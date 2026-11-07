import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

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
        ) as storage_paths, patch(
            "src.application.services.document_processing_service.get_settings",
            return_value=SimpleNamespace(
                OCR_LANGUAGES="eng+ara",
                TESSERACT_CMD=None,
                TESSDATA_DIR=None,
            ),
        ):
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

    def test_scanned_pdf_pages_use_tesseract_ocr(self):
        documents = [
            SimpleNamespace(page_content="", metadata={"page": 0}),
            SimpleNamespace(page_content="existing text", metadata={"page": 1}),
        ]
        pixmap = SimpleNamespace(width=10, height=20, samples=b"rgb")
        first_page = SimpleNamespace(
            get_pixmap=unittest.mock.Mock(return_value=pixmap),
        )
        second_page = SimpleNamespace(
            get_pixmap=unittest.mock.Mock(),
        )
        pdf = MagicMock()
        pdf.__enter__.return_value = [first_page, second_page]

        with (
            patch(
                "src.application.services.document_processing_service.PyMuPDFLoader"
            ) as loader,
            patch(
                "src.application.services.document_processing_service.shutil.which",
                return_value="tesseract.exe",
            ),
            patch(
                "src.application.services.document_processing_service.fitz.open",
                return_value=pdf,
            ),
            patch(
                "src.application.services.document_processing_service.Image.frombytes",
                return_value="image",
            ) as frombytes,
            patch(
                "src.application.services.document_processing_service.pytesseract.image_to_string",
                return_value="recognized text",
            ) as image_to_string,
        ):
            loader.return_value.load.return_value = documents
            self.service.tesseract_cmd = "tesseract.exe"
            result = self.service.load_pdf_with_ocr("scanned.pdf")

        self.assertEqual(result[0].page_content, "recognized text")
        self.assertTrue(result[0].metadata["ocr"])
        self.assertEqual(result[1].page_content, "existing text")
        first_page.get_pixmap.assert_called_once_with(
            dpi=300,
            colorspace=unittest.mock.ANY,
            alpha=False,
        )
        frombytes.assert_called_once_with("RGB", (10, 20), b"rgb")
        image_to_string.assert_called_once_with(
            "image",
            lang="eng+ara",
        )
        second_page.get_pixmap.assert_not_called()

    def test_scanned_pdf_without_tesseract_raises_setup_error(self):
        self.service.tesseract_cmd = None
        with (
            patch(
                "src.application.services.document_processing_service.PyMuPDFLoader"
            ) as loader,
            patch(
                "src.application.services.document_processing_service.shutil.which",
                return_value=None,
            ),
        ):
            loader.return_value.load.return_value = [
                SimpleNamespace(page_content="", metadata={"page": 0})
            ]

            with self.assertRaisesRegex(RuntimeError, "TESSERACT_CMD"):
                self.service.load_pdf_with_ocr("scanned.pdf")

    def test_scanned_pdf_uses_configured_tesseract_and_tessdata_paths(self):
        documents = [SimpleNamespace(page_content="", metadata={})]
        pixmap = SimpleNamespace(width=10, height=20, samples=b"rgb")
        page = SimpleNamespace(get_pixmap=unittest.mock.Mock(return_value=pixmap))
        pdf = MagicMock()
        pdf.__enter__.return_value = [page]

        with tempfile.TemporaryDirectory() as temporary_directory:
            tessdata_path = Path(temporary_directory)
            (tessdata_path / "eng.traineddata").touch()
            (tessdata_path / "ara.traineddata").touch()
            self.service.tessdata_dir = str(tessdata_path)
            with (
                patch(
                    "src.application.services.document_processing_service.PyMuPDFLoader"
                ) as loader,
                patch(
                    "src.application.services.document_processing_service.fitz.open",
                    return_value=pdf,
                ),
                patch(
                    "src.application.services.document_processing_service.Image.frombytes",
                    return_value="image",
                ),
                patch(
                    "src.application.services.document_processing_service.pytesseract.image_to_string",
                    return_value="recognized text",
                ) as image_to_string,
            ):
                loader.return_value.load.return_value = documents
                self.service.tesseract_cmd = "tesseract.exe"
                result = self.service.load_pdf_with_ocr("scanned.pdf")

        self.assertEqual(result[0].page_content, "recognized text")
        image_to_string.assert_called_once_with(
            "image",
            lang="eng+ara",
        )

    def test_service_uses_configured_tesseract_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            executable = root / "tesseract.exe"
            executable.touch()
            tessdata = root / "tessdata"
            tessdata.mkdir()
            settings = SimpleNamespace(
                OCR_LANGUAGES="eng",
                TESSERACT_CMD=str(executable),
                TESSDATA_DIR=str(tessdata),
            )
            with (
                patch(
                    "src.application.services.document_processing_service.get_settings",
                    return_value=settings,
                ),
                patch(
                    "src.application.services.document_processing_service.StoragePaths"
                ) as storage_paths,
                patch(
                    "src.application.services.document_processing_service.pytesseract.pytesseract.tesseract_cmd",
                    "tesseract",
                ),
                patch.dict("os.environ", {"TESSDATA_PREFIX": "previous"}),
            ):
                storage_paths.return_value.get_project_path.return_value = "unused"
                service = DocumentProcessingService(project_id="project-1")
                self.assertEqual(os.environ["TESSDATA_PREFIX"], str(tessdata))

        self.assertEqual(service.tesseract_cmd, str(executable))
        self.assertEqual(service.tessdata_dir, str(tessdata))

    def test_pdf_file_content_uses_ocr_aware_loader(self):
        del self.service.get_file_content
        documents = [SimpleNamespace(page_content="recognized text")]
        with (
            patch.object(
                self.service,
                "load_pdf_with_ocr",
                return_value=documents,
            ) as load_pdf,
            patch(
                "src.application.services.document_processing_service.os.path.exists",
                return_value=True,
            ),
        ):
            result = self.service.get_file_content(
                file_id="scanned.PDF",
                file_path="scanned.PDF",
            )

        self.assertIs(result, documents)
        load_pdf.assert_called_once_with("scanned.PDF")


if __name__ == "__main__":
    unittest.main()
