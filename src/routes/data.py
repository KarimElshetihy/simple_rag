import logging
from fastapi import FastAPI, APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse
from ..helpers.config import Settings, get_settings
from ..controllers import DataController, ProjectController, ProcessController
import os
import aiofiles
from ..schemas.ProcessSchemas import ProcessRequest
from ..enums import ResponseSignal as responseSignal

logger = logging.getLogger("uvicorn.error")

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["data"],
)


@data_router.post("/upload_file/{project_id}")
async def upload_file(
    project_id: str, file: UploadFile, app_settings: Settings = Depends(get_settings)
):

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
async def process_file(project_id: str, process_request: ProcessRequest):

    file_id = process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
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
                }
                for idx, chunk in enumerate(chunks)
            ],
        },
    )
