import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.application.services.document_processing_service import (
    DocumentProcessingService,
)
from src.enums import ResponseSignal


class DocumentProcessingServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.project = SimpleNamespace(id=12, project_id="project-1")
        self.project_repository = SimpleNamespace(
            get_project_or_create=AsyncMock(return_value=self.project)
        )
        self.asset = SimpleNamespace(
            asset_id=34,
            asset_name="document.txt",
            asset_path="unused/document.txt",
        )
        self.asset_repository = SimpleNamespace(
            get_asset_record=AsyncMock(return_value=self.asset),
            get_all_project_assets=AsyncMock(return_value=[self.asset]),
        )
        self.chunk_repository = SimpleNamespace(
            delete_chunks_by_project_id=AsyncMock(return_value=2),
            delete_chunks_by_asset_id=AsyncMock(return_value=2),
            insert_many_chunks=AsyncMock(return_value=1),
        )
        with patch(
            "src.application.services.document_processing_service.StoragePaths"
        ) as storage_paths:
            storage_paths.return_value.get_project_path.return_value = "unused"
            self.service = DocumentProcessingService(project_id="project-1")

        self.service.get_file_content = lambda **kwargs: ["content"]
        self.service.process_file_content = lambda **kwargs: [
            SimpleNamespace(page_content="chunk", metadata={"source": "document"})
        ]

    async def test_processing_one_file_resets_only_that_files_chunks(self):
        result = await self.service.process_project_files(
            project_repository=self.project_repository,
            asset_repository=self.asset_repository,
            chunk_repository=self.chunk_repository,
            file_id="document.txt",
            do_reset=True,
        )

        self.assertEqual(result.signal, ResponseSignal.PROCESSING_SUCCESS)
        self.assertEqual(result.inserted_chunks, 1)
        self.assertEqual(result.processed_files, 1)
        self.chunk_repository.delete_chunks_by_asset_id.assert_awaited_once_with(
            project_id=12, asset_id=34
        )
        self.chunk_repository.delete_chunks_by_project_id.assert_not_awaited()
        inserted_chunks = self.chunk_repository.insert_many_chunks.await_args.kwargs[
            "chunks"
        ]
        self.assertEqual(len(inserted_chunks), 1)
        self.assertEqual(inserted_chunks[0].chunk_project_id, 12)
        self.assertEqual(inserted_chunks[0].chunk_asset_id, 34)

    async def test_processing_all_files_resets_all_project_chunks(self):
        result = await self.service.process_project_files(
            project_repository=self.project_repository,
            asset_repository=self.asset_repository,
            chunk_repository=self.chunk_repository,
            do_reset=True,
        )

        self.assertEqual(result.signal, ResponseSignal.PROCESSING_SUCCESS)
        self.chunk_repository.delete_chunks_by_project_id.assert_awaited_once_with(
            project_id=12
        )
        self.chunk_repository.delete_chunks_by_asset_id.assert_not_awaited()

    async def test_missing_file_returns_error_without_mutating_chunks(self):
        self.asset_repository.get_asset_record.return_value = None

        result = await self.service.process_project_files(
            project_repository=self.project_repository,
            asset_repository=self.asset_repository,
            chunk_repository=self.chunk_repository,
            file_id="missing.txt",
            do_reset=True,
        )

        self.assertEqual(result.signal, ResponseSignal.FILE_ERROR)
        self.chunk_repository.delete_chunks_by_project_id.assert_not_awaited()
        self.chunk_repository.insert_many_chunks.assert_not_awaited()

    async def test_processing_failure_does_not_delete_existing_chunks(self):
        self.service.get_file_content = lambda **kwargs: None

        result = await self.service.process_project_files(
            project_repository=self.project_repository,
            asset_repository=self.asset_repository,
            chunk_repository=self.chunk_repository,
            file_id="document.txt",
            do_reset=True,
        )

        self.assertEqual(result.signal, ResponseSignal.PROCESSING_FAILED)
        self.chunk_repository.delete_chunks_by_project_id.assert_not_awaited()
        self.chunk_repository.insert_many_chunks.assert_not_awaited()

    async def test_empty_chunk_result_is_logged_and_does_not_reset(self):
        self.service.process_file_content = lambda **kwargs: []

        with self.assertLogs("uvicorn.error", level="ERROR") as captured_logs:
            result = await self.service.process_project_files(
                project_repository=self.project_repository,
                asset_repository=self.asset_repository,
                chunk_repository=self.chunk_repository,
                file_id="document.txt",
                do_reset=True,
            )

        self.assertEqual(result.signal, ResponseSignal.PROCESSING_FAILED)
        self.assertIn("No text chunks generated", captured_logs.output[0])
        self.chunk_repository.delete_chunks_by_asset_id.assert_not_awaited()
        self.chunk_repository.insert_many_chunks.assert_not_awaited()

    async def test_processing_uses_the_assets_stored_file_path(self):
        del self.service.get_file_content
        with tempfile.TemporaryDirectory() as temporary_directory:
            stored_path = Path(temporary_directory) / "document.txt"
            stored_path.touch()
            with patch(
                "src.application.services.document_processing_service.TextLoader"
            ) as text_loader:
                text_loader.return_value.load.return_value = [
                    SimpleNamespace(
                        page_content="document text",
                        metadata={"source": "stored path"},
                    )
                ]
                self.asset.asset_path = str(stored_path)

                result = await self.service.process_project_files(
                    project_repository=self.project_repository,
                    asset_repository=self.asset_repository,
                    chunk_repository=self.chunk_repository,
                    file_id="document.txt",
                )

        self.assertEqual(result.signal, ResponseSignal.PROCESSING_SUCCESS)
        text_loader.assert_called_once_with(
            str(stored_path),
            encoding="utf-8",
        )

    async def test_processing_falls_back_to_current_data_directory(self):
        del self.service.get_file_content
        with tempfile.TemporaryDirectory() as temporary_directory:
            current_upload_path = Path(temporary_directory) / "document.txt"
            current_upload_path.write_text("document text", encoding="utf-8")
            self.service.project_path = temporary_directory
            self.asset.asset_path = str(
                Path(temporary_directory) / "legacy" / "document.txt"
            )

            with patch(
                "src.application.services.document_processing_service.TextLoader"
            ) as text_loader:
                text_loader.return_value.load.return_value = [
                    SimpleNamespace(
                        page_content="document text",
                        metadata={"source": "current data directory"},
                    )
                ]

                result = await self.service.process_project_files(
                    project_repository=self.project_repository,
                    asset_repository=self.asset_repository,
                    chunk_repository=self.chunk_repository,
                    file_id="document.txt",
                )

        self.assertEqual(result.signal, ResponseSignal.PROCESSING_SUCCESS)
        text_loader.assert_called_once_with(
            str(current_upload_path),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
