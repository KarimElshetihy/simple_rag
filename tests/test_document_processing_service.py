import unittest
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
        self.asset = SimpleNamespace(asset_id=34, asset_name="document.txt")
        self.asset_repository = SimpleNamespace(
            get_asset_record=AsyncMock(return_value=self.asset),
            get_all_project_assets=AsyncMock(return_value=[self.asset]),
        )
        self.chunk_repository = SimpleNamespace(
            delete_chunks_by_project_id=AsyncMock(return_value=2),
            insert_many_chunks=AsyncMock(return_value=1),
        )
        with patch(
            "src.application.services.document_processing_service.StoragePaths"
        ) as storage_paths:
            storage_paths.return_value.get_project_path.return_value = "unused"
            self.service = DocumentProcessingService(project_id="project-1")

        self.service.get_file_content = lambda file_id: ["content"]
        self.service.process_file_content = lambda **kwargs: [
            SimpleNamespace(page_content="chunk", metadata={"source": "document"})
        ]

    async def test_process_resets_only_after_all_files_are_chunked(self):
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
        self.chunk_repository.delete_chunks_by_project_id.assert_awaited_once_with(
            project_id=12
        )
        inserted_chunks = self.chunk_repository.insert_many_chunks.await_args.kwargs[
            "chunks"
        ]
        self.assertEqual(len(inserted_chunks), 1)
        self.assertEqual(inserted_chunks[0].chunk_project_id, 12)
        self.assertEqual(inserted_chunks[0].chunk_asset_id, 34)

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
        self.service.get_file_content = lambda file_id: None

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


if __name__ == "__main__":
    unittest.main()
