import logging

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse
from kombu.exceptions import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ..helpers.db import get_db_session
from ..helpers.timing import log_async_duration
from ..application.services.data_service import DataService, FileUploadError
from ..schemas.process_schemas import ProcessRequest
from ..enums import ResponseSignal as responseSignal
from ..infrastructure.celery.tasks import process_project_files
from ..infrastructure.database.repositories import (
    AssetRepository,
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
        async with log_async_duration(
            "request.upload_file", project_id=project_id
        ):
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
):
    try:
        async with log_async_duration(
            "request.enqueue_process_files", project_id=project_id
        ):
            task = await run_in_threadpool(
                process_project_files.delay,
                project_id=project_id,
                file_id=process_request.file_id,
                chunk_size=process_request.chunk_size,
                overlap_size=process_request.overlap_size,
                do_reset=process_request.do_reset,
            )
    except OperationalError:
        logger.exception(
            "Failed to enqueue document processing for project %s",
            project_id,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"message": "processing_queue_unavailable"},
        )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "message": "processing_queued",
            "task_id": task.id,
        },
    )
