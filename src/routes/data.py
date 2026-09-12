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
from ..models.db_schemes import Chunk

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

    project_model = await ProjectModel.creaate_instance(db_client=request.app.state.db)
    project = await project_model.get_project_or_create(project_id=project_id)

    data_controller = DataController()
    project_controller = ProjectController()

    is_valid, validation_message = DataController().validate_uploaded_file(file=file)

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"message": validation_message},
        )

    else:
        project_path = project_controller.get_project_path(project_id=project_id)

        new_file_path, unique_file_name = data_controller.generate_unique_file_path(
            orig_file_name=file.filename,
            project_id=project_id,
        )

        upload_message = await data_controller.upload_file_to_path(
            file=file, file_path=new_file_path
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "Validation Message": validation_message,
                "Upload Message": upload_message,
                "file_name": file.filename,
                "file_size": file.size,
            },
        )


@data_router.post("/process_file/{project_id}")
async def process_file(
    request: Request, project_id: str, process_request: ProcessRequest
):

    file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset = process_request.do_reset
    process_controller = ProcessController(project_id=project_id)
    file_content = process_controller.get_file_content(file_id=file_id)

    project_model = await ProjectModel.creaate_instance(db_client=request.app.state.db)
    project = await project_model.get_project_or_create(project_id=project_id)
    process_controller = ProcessController(project_id=project_id)
    file_content = process_controller.get_file_content(file_id=file_id)

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
        )
        for i, chunk in enumerate(chunks)
    ]

    chunk_model = await ChunkModel.creaate_instance(db_client=request.app.state.db)

    if do_reset == 1:
        _ = await chunk_model.delete_chunks_by_project_id(project_id=project.id)

    no_records = await chunk_model.insert_many_chunks(chunks=file_chunks_records)

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "message": responseSignal.PROCESSING_SUCCESS.value,
            "total_chunks": len(chunks),
            "chunks": [
                {
                    "chunk_id": idx + 1,
                    "chunk_content": chunk.page_content,
                    "chunk_metadata": chunk.metadata,
                    "chunks_no": no_records,
                }
                for idx, chunk in enumerate(chunks)
            ],
        },
    )
