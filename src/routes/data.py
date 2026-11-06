import logging

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..helpers.db import get_db_session
from ..application.services.data_service import DataService, FileUploadError
from ..application.services.document_processing_service import (
    DocumentProcessingService,
)
from ..schemas.process_schemas import ProcessRequest
from ..enums import ResponseSignal as responseSignal
from ..infrastructure.database.repositories import (
    AssetRepository,
    ChunkRepository,
    ProjectRepository,
)

logger = logging.getLogger("uvicorn.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["data"],
)


@data_router.post("/upload_file/{project_id}")
async def upload_file(
    project_id: str,
    file: UploadFile,
    session: AsyncSession = Depends(get_db_session),
):
    data_service = DataService()
    is_valid, validation_message = data_service.validate_uploaded_file(file=file)

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": validation_message},
        )

    try:
        result = await data_service.upload_and_register_file(
            file=file,
            project_id=project_id,
            project_repository=ProjectRepository(session),
            asset_repository=AssetRepository(session),
        )
    except FileUploadError:
        logger.exception("Failed to upload file for project %s", project_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": responseSignal.FILE_UPLOAD_FAILED.value},
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "Validation Message": validation_message,
            "Upload Message": result.upload_message,
            "file_name": file.filename,
            "file_size": file.size,
            "asset": result.asset.asset_name,
            "asset_type": result.asset.asset_type,
            "asset_project": result.project.project_id,
        },
    )


@data_router.post("/process_file/{project_id}")
async def process_file(
    project_id: str,
    process_request: ProcessRequest,
    session: AsyncSession = Depends(get_db_session),
):
    processing_service = DocumentProcessingService(project_id=project_id)
    result = await processing_service.process_project_files(
        project_repository=ProjectRepository(session),
        asset_repository=AssetRepository(session),
        chunk_repository=ChunkRepository(session),
        file_id=process_request.file_id,
        chunk_size=process_request.chunk_size,
        overlap_size=process_request.overlap_size,
        do_reset=process_request.do_reset,
    )
    if result.signal != responseSignal.PROCESSING_SUCCESS:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": result.signal.value},
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": result.signal.value,
            "inserted_chaunks": result.inserted_chunks,
            "processed_file": result.processed_files,
        },
    )
