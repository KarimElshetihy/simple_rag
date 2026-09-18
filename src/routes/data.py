import logging
from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
from ..helpers.config import Settings, get_settings
from ..controllers import DataController, ProjectController, ProcessController
import os
import aiofiles
from ..schemas.ProcessSchemas import ProcessRequest
from ..enums import ResponseSignal as responseSignal
from ..models.ProjectModel import ProjectModel
from ..models.ChunkModel import ChunkModel
from ..models.AssetModel import AssetModel
from ..models.db_schemes import Chunk
from ..models.db_schemes import Asset
from ..enums.AssetEnums import AssetTypeEnum

logger = logging.getLogger("uvicorn.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["data"],
)


@data_router.post("/upload_file/{project_id}")
async def upload_file(
    request: Request,
    project_id: str,
    file: UploadFile,
    app_settings: Settings = Depends(get_settings),
):

    project_model = await ProjectModel.create_instance(db_client=request.app.state.db)
    project = await project_model.get_project_or_create(project_id=project_id)

    data_controller = DataController()
    project_controller = ProjectController()

    is_valid, validation_message = DataController().validate_uploaded_file(file=file)

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": validation_message},
        )

    
    project_path = project_controller.get_project_path(project_id=project_id)

    new_file_path, unique_file_name = data_controller.generate_unique_file_path(
        orig_file_name=file.filename,
        project_id=project_id,
    )

    upload_message = await data_controller.upload_file_to_path(
        file=file, file_path=new_file_path
    )

    asset_model = await AssetModel.create_instance(db_client=request.app.state.db)

    asset_resource = Asset(
        asset_project_id=project.id,
        asset_type=AssetTypeEnum.FILE.value,
        asset_name=unique_file_name,
        asset_size=file.size,
        asset_path=new_file_path,
        asset_original_name=file.filename
    )

    asset_record = await asset_model.create_asset(asset=asset_resource)


    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "Validation Message": validation_message,
            "Upload Message": upload_message,
            "file_name": file.filename,
            "file_size": file.size,
            "asset":asset_record.asset_name,
            "asset_type":asset_record.asset_type,
            # "asset_project":asset_record.asset_project_id
        },
    )


@data_router.post("/process_file/{project_id}")
async def process_file(
    request: Request, project_id: str, process_request: ProcessRequest
):

    # file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset
    process_controller = ProcessController(project_id=project_id)
    # file_content = process_controller.get_file_content(file_id=file_id)

    project_model = await ProjectModel.create_instance(db_client=request.app.state.db)
    project = await project_model.get_project_or_create(project_id=project_id)

    asset_model = await AssetModel.create_instance(db_client=request.app.state.db)

    project_file_ids = {}
    if process_request.file_id:
        asset_record = await asset_model.get_asset_record(asset_project_id=project.id, asset_name=process_request.file_id)

        if not asset_record:
            return JSONResponse(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        content={"message": responseSignal.FILE_ERROR.value},
                    ) 

        project_file_ids = {asset_record.id: asset_record.asset_name}
    else:
        project_files = await asset_model.get_all_project_assets(asset_project_id=project.id, asset_type=AssetTypeEnum.FILE.value)
        project_file_ids = {record.id: record.asset_name for record in project_files}

        if len(project_file_ids) == 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": responseSignal.NO_PROJECT_FILES_ERROR.value},
            )

    process_controller = ProcessController(project_id=project_id)

    chunk_model = await ChunkModel.create_instance(db_client=request.app.state.db)

    if do_reset == 1:
        _ = await chunk_model.delete_chunks_by_project_id(project_id=project.id)


    no_records = 0
    no_files = 0
    for asset_id, file_id in project_file_ids.items():
        file_content = process_controller.get_file_content(file_id=file_id)

        if not file_content:
            logger.error(f"Error while processing the file: {file_id}")
        
        chunks = process_controller.process_file_content(
            file_content=file_content,
            file_id=file_id,
            chunk_size=chunk_size,
            overlap_size=overlap_size,
        )

        if chunks is None or len(chunks) == 0:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"message": responseSignal.FILE_PROCESSING_FAILED.value},
            )

        file_chunks_records = [
            Chunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=i + 1,
                chunk_project_id=project.id,
                chunk_asset_id=asset_id,
            )
            for i, chunk in enumerate(chunks)
        ]

        

        
        no_records += await chunk_model.insert_many_chunks(chunks=file_chunks_records)
        no_files += 1

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": responseSignal.PROCESSING_SUCCESS.value,
            "inserted_chaunks": no_records,
            "processed_file": no_files,
        },
    )
