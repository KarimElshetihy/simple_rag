import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.application.services.document_processing_service import (
    DocumentProcessingService,
)
from src.enums.database_enums import BackendDBEnum
from src.enums.response_enums import ResponseSignal
from src.helpers.config import get_settings
from src.infrastructure.celery.app import celery_app
from src.infrastructure.database.repositories import (
    AssetRepository,
    ChunkRepository,
    ProjectRepository,
)


async def _process_project_files(
    project_id: str,
    file_id: str | None,
    chunk_size: int,
    overlap_size: int,
    do_reset: bool,
) -> dict[str, int | str]:
    settings = get_settings()

    if settings.DATABASE_BACKEND != BackendDBEnum.POSTGRES:
        raise ValueError(
            f"{settings.DATABASE_BACKEND.value} is not configured; "
            "this application currently supports PostgreSQL only."
        )
    if not settings.POSTGRES_URI:
        raise ValueError("POSTGRES_URI must be configured for PostgreSQL.")

    engine = create_async_engine(settings.POSTGRES_URI)
    try:
        session_factory = async_sessionmaker(
            engine,
            expire_on_commit=False,
        )
        async with session_factory() as session:
            async with session.begin():
                service = DocumentProcessingService(project_id=project_id)
                result = await service.process_project_files(
                    project_repository=ProjectRepository(session),
                    asset_repository=AssetRepository(session),
                    chunk_repository=ChunkRepository(session),
                    file_id=file_id,
                    chunk_size=chunk_size,
                    overlap_size=overlap_size,
                    do_reset=do_reset,
                )
                if result.signal != ResponseSignal.PROCESSING_SUCCESS:
                    raise RuntimeError(
                        f"Document processing failed: {result.signal.value}"
                    )

                return {
                    "signal": result.signal.value,
                    "inserted_chunks": result.inserted_chunks,
                    "processed_files": result.processed_files,
                }
    finally:
        await engine.dispose()


@celery_app.task(name="documents.process_project_files")
def process_project_files(
    project_id: str,
    file_id: str | None = None,
    chunk_size: int = 1000,
    overlap_size: int = 150,
    do_reset: bool = False,
) -> dict[str, int | str]:
    return asyncio.run(
        _process_project_files(
            project_id=project_id,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
            do_reset=do_reset,
        )
    )
