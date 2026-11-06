import logging

from fastapi import APIRouter, Depends, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..helpers.db import get_db_session
from ..models.ProjectModel import ProjectModel
from ..schemas.VectorsSchema import PushRequest, SearchRequest
from ..controllers.VectorsController import VectorsController
from ..enums import ResponseSignal
from ..models.ChunkModel import ChunkModel

logger = logging.getLogger("uvicorn.error")

vectors_router = APIRouter(
    prefix="/api/v1/vectors",tags=["vectors"],)

@vectors_router.post("/index_vector/{project_id}")
async def index_vector(
    request: Request,
    project_id: str,
    push_request: PushRequest,
    session: AsyncSession = Depends(get_db_session),
):
    project_model = ProjectModel(session)

    project = await project_model.get_project_or_create(project_id=project_id)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.PROJECT_NOT_FOUND_ERROR.value
            }
        )
    
    vec_controller = VectorsController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )

    has_records = True
    page_no = 1
    inserted_items_count = 0

    chunk_model = ChunkModel(session)
    staging_collection = (
        vec_controller.create_staging_collection_name()
        if push_request.do_reset
        else None
    )
    target_collection = staging_collection or vec_controller.create_collection_name(
        project_id=project.project_id
    )
    collection_published = False

    try:
        while has_records:
            page_chunks = await chunk_model.get_poject_chunks(
                project_id=project.id,
                page_no=page_no,
            )

            if page_chunks:
                page_no += 1

            if not page_chunks:
                has_records = False
                break

            is_inserted = await vec_controller.index_into_vector_db(
                project=project,
                chunks=page_chunks,
                collection_name=target_collection,
            )

            if not is_inserted:
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "signal": ResponseSignal.INSERT_INTO_VECTORDB_ERROR.value
                    },
                )

            inserted_items_count += len(page_chunks)

        if inserted_items_count:
            await vec_controller.ensure_vector_index(
                project=project,
                collection_name=target_collection,
            )
            if staging_collection:
                await vec_controller.publish_vector_collection(
                    staging_collection=staging_collection,
                    project=project,
                )
                collection_published = True

        return JSONResponse(
            content={
                "signal": ResponseSignal.INSERT_INTO_VECTORDB_SUCCESS.value,
                "inserted_items_count": inserted_items_count,
            }
        )
    finally:
        if staging_collection and not collection_published:
            try:
                await request.app.vector_db_client.delete_collection(
                    collection_name=staging_collection
                )
            except Exception:
                logger.exception(
                    "Failed to clean up staging vector collection %s",
                    staging_collection,
                )

@vectors_router.get("/index/info/{project_id}")
async def get_project_index_info(
    request: Request,
    project_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    
    project_model = ProjectModel(session)

    project = await project_model.get_project_or_create(
        project_id=project_id
    )

    vec_controller = VectorsController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )

    collection_info = await vec_controller.get_vector_db_collection_info(
        project=project
    )

    return JSONResponse(
        content={
            "signal": ResponseSignal.VECTORDB_COLLECTION_RETRIEVED.value,
            "collection_info": collection_info
        }
    )

@vectors_router.post("/index/search/{project_id}")
async def search_index(
    request: Request,
    project_id: str,
    search_request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
):
    
    project_model = ProjectModel(session)

    project = await project_model.get_project_or_create(
        project_id=project_id
    )

    vec_controller = VectorsController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    results = await vec_controller.search_vector_db_collection(
        project=project, text=search_request.text, limit=search_request.limit
    )

    if not results:
        return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseSignal.VECTORDB_SEARCH_ERROR.value
                }
            )
    
    return JSONResponse(
        content={
            "signal": ResponseSignal.VECTORDB_SEARCH_SUCCESS.value,
            "results": [result.model_dump(exclude_none=True) for result in results]
        }
    )

@vectors_router.post("/index/answer/{project_id}")
async def answer_rag(
    request: Request,
    project_id: str,
    search_request: SearchRequest,
    session: AsyncSession = Depends(get_db_session),
):
    
    project_model = ProjectModel(session)

    project = await project_model.get_project_or_create(
        project_id=project_id
    )

    vec_controller = VectorsController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    answer, full_prompt, chat_history = await vec_controller.answer_rag_question(
        project=project,
        query=search_request.text,
        limit=search_request.limit,
    )

    if not answer:
        return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseSignal.RAG_ANSWER_ERROR.value
                }
        )
    
    return JSONResponse(
        content={
            "signal": ResponseSignal.RAG_ANSWER_SUCCESS.value,
            "answer": answer,
            "full_prompt": full_prompt,
            "chat_history": chat_history
        }
    )