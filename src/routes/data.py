import logging
import os

from fastapi import APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession

from ..helpers.db import get_db_session
from ..controllers import DataController, ProcessController
from ..schemas.ProcessSchemas import ProcessRequest
from ..enums import ResponseSignal as responseSignal
from ..models.ProjectModel import ProjectModel
from ..models.ChunkModel import ChunkModel
from ..models.AssetModel import AssetModel
from ..models.db_schemes.db_rag.schemes.chunk import AssetChunk
from ..models.db_schemes.db_rag.schemes.asset import Asset
from ..enums.AssetEnums import AssetTypeEnum

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
    data_controller = DataController()
    is_valid, validation_message = data_controller.validate_uploaded_file(file=file)

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": validation_message},
        )

    new_file_path, unique_file_name = data_controller.generate_unique_file_path(
        orig_file_name=file.filename,
        project_id=project_id,
    )

    try:
        upload_message = await data_controller.upload_file_to_path(
            file=file, file_path=new_file_path
        )
    except Exception:
        logger.exception("Failed to upload file for project %s", project_id)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"message": responseSignal.FILE_UPLOAD_FAILED.value},
        )

    try:
        project_model = ProjectModel(session)
        project = await project_model.get_project_or_create(project_id=project_id)

        asset_model = AssetModel(session)
        asset_resource = Asset(
            asset_project_id=project.id,
            asset_type=AssetTypeEnum.FILE.value,
            asset_name=unique_file_name,
            asset_size=file.size,
            asset_path=new_file_path,
            asset_original_name=file.filename,
        )
        asset_record = await asset_model.create_asset(asset=asset_resource)
    except Exception:
        try:
            os.remove(new_file_path)
        except FileNotFoundError:
            pass
        except OSError:
            logger.exception("Failed to remove uploaded file %s", new_file_path)
        raise

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "Validation Message": validation_message,
            "Upload Message": upload_message,
            "file_name": file.filename,
            "file_size": file.size,
            "asset": asset_record.asset_name,
            "asset_type": asset_record.asset_type,
            "asset_project": project.project_id,
        },
    )


@data_router.post("/process_file/{project_id}")
async def process_file(
    project_id: str,
    process_request: ProcessRequest,
    session: AsyncSession = Depends(get_db_session),
):
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset

    project_model = ProjectModel(session)
    project = await project_model.get_project_or_create(project_id=project_id)

    asset_model = AssetModel(session)
    project_file_ids = {}
    if process_request.file_id:
        asset_record = await asset_model.get_asset_record(
            asset_project_id=project.id, asset_name=process_request.file_id
        )

        if not asset_record:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": responseSignal.FILE_ERROR.value},
            )

        project_file_ids = {asset_record.asset_id: asset_record.asset_name}
    else:
        project_files = await asset_model.get_all_project_assets(
            asset_project_id=project.id, asset_type=AssetTypeEnum.FILE.value
        )
        project_file_ids = {
            record.asset_id: record.asset_name for record in project_files
        }

        if not project_file_ids:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": responseSignal.NO_PROJECT_FILES_ERROR.value},
            )

    process_controller = ProcessController(project_id=project_id)
    chunk_model = ChunkModel(session)
    file_chunks_records = []
    for asset_id, file_id in project_file_ids.items():
        file_content = await run_in_threadpool(
            process_controller.get_file_content, file_id=file_id
        )

        if not file_content:
            logger.error("Error while processing the file: %s", file_id)
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": responseSignal.PROCESSING_FAILED.value},
            )

        chunks = await run_in_threadpool(
            process_controller.process_file_content,
            file_content=file_content,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
        )

        if not chunks:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": responseSignal.PROCESSING_FAILED.value},
            )

        file_chunks_records.extend(
            AssetChunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=i + 1,
                chunk_project_id=project.id,
                chunk_asset_id=asset_id,
            )
            for i, chunk in enumerate(chunks)
        )

    if do_reset:
        await chunk_model.delete_chunks_by_project_id(project_id=project.id)

    no_records = await chunk_model.insert_many_chunks(chunks=file_chunks_records)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": responseSignal.PROCESSING_SUCCESS.value,
            "inserted_chaunks": no_records,
            "processed_file": len(project_file_ids),
        },
    )
