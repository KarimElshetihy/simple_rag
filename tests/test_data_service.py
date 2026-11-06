import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.application.services.data_service import DataService, FileUploadError
from src.enums import ResponseSignal


class DataServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            DATA_DIR="unused-test-data",
            FILE_SUPPORTED_TYPES=["text/plain"],
            FILE_MAX_SIZE=10,
            FILE_DEFAULT_CHUNK_SIZE=1024,
        )
        self.project = SimpleNamespace(id=1, project_id="project-1")
        self.asset = SimpleNamespace(
            asset_name="unique_document.txt",
            asset_type="FILE",
        )
        self.project_repository = SimpleNamespace(
            get_project_or_create=AsyncMock(return_value=self.project)
        )
        self.asset_repository = SimpleNamespace(
            create_asset=AsyncMock(return_value=self.asset)
        )
        with (
            patch(
                "src.application.services.data_service.get_settings",
                return_value=self.settings,
            ),
            patch("src.application.services.data_service.StoragePaths"),
        ):
            self.service = DataService()
        self.service.generate_unique_file_path = lambda **kwargs: (
            "unused-path",
            "unique_document.txt",
        )

    async def test_upload_and_asset_registration_returns_persisted_records(self):
        upload_file = SimpleNamespace(filename="document.txt", size=12)
        self.service.upload_file_to_path = AsyncMock(
            return_value=ResponseSignal.FILE_UPLOAD_SUCCESS.value
        )

        result = await self.service.upload_and_register_file(
            file=upload_file,
            project_id="project-1",
            project_repository=self.project_repository,
            asset_repository=self.asset_repository,
        )

        self.assertIs(result.project, self.project)
        self.assertIs(result.asset, self.asset)
        self.assertEqual(
            result.upload_message,
            ResponseSignal.FILE_UPLOAD_SUCCESS.value,
        )
        self.project_repository.get_project_or_create.assert_awaited_once_with(
            project_id="project-1"
        )
        self.asset_repository.create_asset.assert_awaited_once()

    async def test_registration_failure_removes_the_uploaded_file(self):
        upload_file = SimpleNamespace(filename="document.txt", size=12)
        self.asset_repository.create_asset.side_effect = RuntimeError("db failure")

        with tempfile.TemporaryDirectory() as temporary_directory:
            file_path = Path(temporary_directory) / "uploaded.txt"
            self.service.generate_unique_file_path = lambda **kwargs: (
                str(file_path),
                "unique_document.txt",
            )

            async def write_upload(file, file_path):
                Path(file_path).write_text("uploaded", encoding="utf-8")
                return ResponseSignal.FILE_UPLOAD_SUCCESS.value

            self.service.upload_file_to_path = write_upload

            with self.assertRaisesRegex(RuntimeError, "db failure"):
                await self.service.upload_and_register_file(
                    file=upload_file,
                    project_id="project-1",
                    project_repository=self.project_repository,
                    asset_repository=self.asset_repository,
                )

            self.assertFalse(file_path.exists())

    async def test_upload_failure_is_distinguished_from_registration_failure(self):
        self.service.upload_file_to_path = AsyncMock(
            side_effect=OSError("disk failure")
        )

        with self.assertRaises(FileUploadError) as error:
            await self.service.upload_and_register_file(
                file=SimpleNamespace(filename="document.txt", size=12),
                project_id="project-1",
                project_repository=self.project_repository,
                asset_repository=self.asset_repository,
            )

        self.assertIsInstance(error.exception.__cause__, OSError)
        self.project_repository.get_project_or_create.assert_not_awaited()
        self.asset_repository.create_asset.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
