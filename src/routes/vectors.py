from fastapi import APIRouter, Depends, status, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from ..helpers.db import get_db_session
from ..helpers.timing import log_async_duration
from ..schemas.vectors_schema import PushRequest, SearchRequest
from ..application.services.rag_service import RagService
from ..enums import ResponseSignal
from ..infrastructure.database.repositories import ChunkRepository, ProjectRepository

vectors_router = APIRouter(
    prefix="/api/v1/vectors",tags=["vectors"],)

@vectors_router.post("/index_vector/{project_id}")
async def index_vector(
    request: Request,
    project_id: str,
    push_request: PushRequest,
    session: AsyncSession = Depends(get_db_session),
):
    rag_service = RagService(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )

    async with log_async_duration(
        "request.index_project", project_id=project_id
    ):
        result = await rag_service.index_project_chunks(
            project_id=project_id,
            project_repository=ProjectRepository(session),
            chunk_repository=ChunkRepository(session),
            do_reset=push_request.do_reset,
        )
    if result.signal != ResponseSignal.INSERT_INTO_VECTORDB_SUCCESS:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal": result.signal.value},
        )

    return JSONResponse(
        content={
            "signal": result.signal.value,
            "inserted_items_count": result.inserted_items_count,
        }
    )

@vectors_router.get("/index/info/{project_id}")
async def get_project_index_info(
    request: Request,
    project_id: str,
    session: AsyncSession = Depends(get_db_session),
):
    
    rag_service = RagService(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser
    )

    collection_info = await rag_service.get_project_collection_info(
        project_id=project_id,
        project_repository=ProjectRepository(session),
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
    
    rag_service = RagService(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    async with log_async_duration(
        "request.search_project", project_id=project_id
    ):
        results = await rag_service.search_project(
            project_id=project_id,
            text=search_request.text,
            project_repository=ProjectRepository(session),
            limit=search_request.limit,
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
    
    rag_service = RagService(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    async with log_async_duration(
        "request.answer_question", project_id=project_id
    ):
        answer, full_prompt, chat_history = await rag_service.answer_project_question(
            project_id=project_id,
            query=search_request.text,
            project_repository=ProjectRepository(session),
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