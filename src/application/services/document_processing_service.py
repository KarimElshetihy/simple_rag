import logging
import os
from dataclasses import dataclass

from starlette.concurrency import run_in_threadpool
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.enums import ProcessEnum
from src.enums import ResponseSignal
from src.enums.asset_enums import AssetTypeEnum
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
        self.project_path = StoragePaths().get_project_path(project_id=project_id)

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
                await chunk_repository.delete_chunks_by_asset_id(
                    project_id=project.id,
                    asset_id=project_files[0].asset_id,
                )
            else:
                await chunk_repository.delete_chunks_by_project_id(
                    project_id=project.id
                )

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
        return os.path.splitext(file_id)[-1]

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

    def get_file_content(self, file_id: str, file_path: str | None = None):

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
