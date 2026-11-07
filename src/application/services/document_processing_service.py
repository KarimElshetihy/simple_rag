import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image
import pytesseract
from starlette.concurrency import run_in_threadpool
from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.enums import ProcessEnum
from src.enums import ResponseSignal
from src.enums.asset_enums import AssetTypeEnum
from src.helpers.timing import log_async_duration, log_duration
from src.helpers.config import get_settings
from src.infrastructure.database.repositories import (
    AssetRepository,
    ChunkRepository,
    ProjectRepository,
)
from src.infrastructure.filesystem import StoragePaths
from src.models.db_schemes.db_rag.schemes.chunk import AssetChunk


logger = logging.getLogger("uvicorn.error")


@dataclass
class ProcessFilesResult:
    signal: ResponseSignal
    inserted_chunks: int = 0
    processed_files: int = 0


class DocumentProcessingService:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.app_settings = get_settings()
        configured_tesseract = self.app_settings.TESSERACT_CMD
        self.tesseract_cmd = self.resolve_tesseract_command(configured_tesseract)
        configured_tessdata = self.app_settings.TESSDATA_DIR
        self.tessdata_dir = configured_tessdata or (
            str(Path(self.tesseract_cmd).parent / "tessdata")
            if self.tesseract_cmd
            else None
        )
        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd
        if self.tessdata_dir:
            os.environ["TESSDATA_PREFIX"] = self.tessdata_dir
        self.project_path = StoragePaths().get_project_path(project_id=project_id)

    @staticmethod
    def resolve_tesseract_command(configured_command: str | None) -> str | None:
        if configured_command:
            if os.path.isfile(configured_command):
                return configured_command
            return shutil.which(configured_command)

        executable = shutil.which("tesseract")
        if executable:
            return executable

        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        standard_install = (
            Path(program_files) / "Tesseract-OCR" / "tesseract.exe"
        )
        return str(standard_install) if standard_install.is_file() else None

    async def process_project_files(
        self,
        project_repository: ProjectRepository,
        asset_repository: AssetRepository,
        chunk_repository: ChunkRepository,
        file_id: str | None = None,
        chunk_size: int = 1000,
        overlap_size: int = 150,
        do_reset: bool = False,
    ) -> ProcessFilesResult:
        project = await project_repository.get_project_or_create(
            project_id=self.project_id
        )

        if file_id:
            asset_record = await asset_repository.get_asset_record(
                asset_project_id=project.id,
                asset_name=file_id,
            )
            if not asset_record:
                return ProcessFilesResult(signal=ResponseSignal.FILE_ERROR)
            project_files = [asset_record]
        else:
            project_files = await asset_repository.get_all_project_assets(
                asset_project_id=project.id,
                asset_type=AssetTypeEnum.FILE.value,
            )
            if not project_files:
                return ProcessFilesResult(
                    signal=ResponseSignal.NO_PROJECT_FILES_ERROR
                )

        file_chunks_records = []
        for asset_record in project_files:
            current_file_id = asset_record.asset_name
            current_file_path = self.get_asset_file_path(
                asset_path=asset_record.asset_path,
                file_id=current_file_id,
            )
            async with log_async_duration(
                "document.load_file",
                project_id=self.project_id,
                asset_id=asset_record.asset_id,
            ):
                file_content = await run_in_threadpool(
                    self.get_file_content,
                    file_id=current_file_id,
                    file_path=current_file_path,
                )
            if not file_content:
                if not os.path.isfile(current_file_path):
                    reason = "file is missing from project storage"
                elif self.get_file_extension(current_file_id) not in {
                    ProcessEnum.TXT.value,
                    ProcessEnum.PDF.value,
                }:
                    reason = "file extension is not supported"
                else:
                    reason = "file loader returned no content"
                logger.error(
                    "Failed to load project asset %s for project %s: %s",
                    current_file_id,
                    self.project_id,
                    f"{reason} (path: {current_file_path}; "
                    f"database path: {asset_record.asset_path})",
                )
                return ProcessFilesResult(signal=ResponseSignal.PROCESSING_FAILED)

            async with log_async_duration(
                "document.chunk_file",
                project_id=self.project_id,
                asset_id=asset_record.asset_id,
            ):
                chunks = await run_in_threadpool(
                    self.process_file_content,
                    file_content=file_content,
                    chunk_size=chunk_size,
                    overlap_size=overlap_size,
                )
            if not chunks:
                logger.error(
                    "No text chunks generated for project asset %s in project %s",
                    current_file_id,
                    self.project_id,
                )
                return ProcessFilesResult(signal=ResponseSignal.PROCESSING_FAILED)

            file_chunks_records.extend(
                AssetChunk(
                    chunk_text=chunk.page_content,
                    chunk_metadata=chunk.metadata,
                    chunk_order=index + 1,
                    chunk_project_id=project.id,
                    chunk_asset_id=asset_record.asset_id,
                )
                for index, chunk in enumerate(chunks)
            )

        if do_reset:
            if file_id:
                async with log_async_duration(
                    "document.delete_asset_chunks",
                    project_id=self.project_id,
                    asset_id=project_files[0].asset_id,
                ):
                    await chunk_repository.delete_chunks_by_asset_id(
                        project_id=project.id,
                        asset_id=project_files[0].asset_id,
                    )
            else:
                async with log_async_duration(
                    "document.delete_project_chunks",
                    project_id=self.project_id,
                ):
                    await chunk_repository.delete_chunks_by_project_id(
                        project_id=project.id
                    )

        async with log_async_duration(
            "document.insert_chunks",
            project_id=self.project_id,
            chunks=len(file_chunks_records),
        ):
            inserted_chunks = await chunk_repository.insert_many_chunks(
                chunks=file_chunks_records
            )
        return ProcessFilesResult(
            signal=ResponseSignal.PROCESSING_SUCCESS,
            inserted_chunks=inserted_chunks,
            processed_files=len(project_files),
        )

    def get_asset_file_path(self, asset_path: str, file_id: str) -> str:
        if os.path.isfile(asset_path):
            return asset_path
        return os.path.join(self.project_path, file_id)

    def get_file_extension(self, file_id: str):
        return os.path.splitext(file_id)[-1].lower()

    def get_file_loader(self, file_id: str, file_path: str | None = None):

        file_ext = self.get_file_extension(file_id=file_id)
        if file_path is None:
            file_path = os.path.join(self.project_path, file_id)

        if not os.path.exists(file_path):
            return None

        if file_ext == ProcessEnum.TXT.value:
            return TextLoader(file_path, encoding="utf-8")

        if file_ext == ProcessEnum.PDF.value:
            return PyMuPDFLoader(file_path)

        return None

    def load_pdf_with_ocr(self, file_path: str) -> list[Document]:
        documents = PyMuPDFLoader(file_path).load()
        pages_to_ocr = [
            page_number
            for page_number, document in enumerate(documents)
            if not document.page_content.strip()
        ]
        if not pages_to_ocr:
            return documents

        if self.tesseract_cmd is None:
            raise RuntimeError(
                "Tesseract is required to OCR scanned PDF pages. "
                "Install it and set TESSERACT_CMD to the executable path."
            )

        language = self.app_settings.OCR_LANGUAGES
        tessdata_dir = self.tessdata_dir
        if tessdata_dir:
            tessdata_path = Path(tessdata_dir).expanduser()
            if not tessdata_path.is_dir():
                raise RuntimeError(
                    f"TESSDATA_DIR does not exist or is not a directory: "
                    f"{tessdata_dir}"
                )
            missing_languages = [
                language_code
                for language_code in language.split("+")
                if not (tessdata_path / f"{language_code}.traineddata").is_file()
            ]
            if missing_languages:
                raise RuntimeError(
                    "Tesseract language data is missing from TESSDATA_DIR: "
                    + ", ".join(missing_languages)
                )

        with fitz.open(file_path) as pdf:
            for page_number in pages_to_ocr:
                page = pdf[page_number]
                with log_duration(
                    "document.ocr_page",
                    project_id=self.project_id,
                    page=page_number + 1,
                ):
                    pixmap = page.get_pixmap(
                        dpi=300,
                        colorspace=fitz.csRGB,
                        alpha=False,
                    )
                    image = Image.frombytes(
                        "RGB",
                        (pixmap.width, pixmap.height),
                        pixmap.samples,
                    )
                    documents[page_number].page_content = (
                        pytesseract.image_to_string(
                            image,
                            lang=language,
                        ).strip()
                    )
                documents[page_number].metadata["ocr"] = True

        return documents

    def get_file_content(self, file_id: str, file_path: str | None = None):
        if self.get_file_extension(file_id) == ProcessEnum.PDF.value:
            if file_path is None:
                file_path = os.path.join(self.project_path, file_id)
            if not os.path.exists(file_path):
                return None
            return self.load_pdf_with_ocr(file_path)

        loader = self.get_file_loader(file_id=file_id, file_path=file_path)

        if not loader:
            return None
        
        return loader.load()

    def process_file_content(
        self,
        file_content: list,
        chunk_size: int = 1000,
        overlap_size: int = 150,
    ):
        if chunk_size <= 0 or chunk_size > 8192:
            raise ValueError("Chunk size must be between 1 and 8192 characters.")
        if overlap_size < 0 or overlap_size >= chunk_size:
            raise ValueError(
                "Chunk overlap must be non-negative and smaller than chunk size."
            )

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=overlap_size,
            length_function=len,
            separators=[
                "\n\n",
                "\n",
                r"(?<=[؟؛۔])(?=\s|$)",
                r"(?<=[.!?])(?=\s|$)",
                r"(?<=[،,])(?=\s|$)",
                r"\s+",
                "",
            ],
            is_separator_regex=True,
            add_start_index=True,
        )

        file_content_texts = [rec.page_content for rec in file_content]

        file_content_metadata = [rec.metadata for rec in file_content]

        chunks = text_splitter.create_documents(
            file_content_texts, metadatas=file_content_metadata
        )

        return chunks
