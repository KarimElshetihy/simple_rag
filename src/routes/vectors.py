from fastapi import FastAPI, APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
import logging
from ..models.ProjectModel import ProjectModel
from ..schemas.VectorsSchema import PushRequest, SearchRequest
from ..controllers.VectorsController import VectorsController
from ..enums import ResponseSignal
from ..models.ChunkModel import ChunkModel

logger = logging.getLogger("uvicorn.error")

vectors_router = APIRouter(
    prefix="/api/v1/vectors",tags=["vectors"],)

@vectors_router.post("/index_vector/{project_id}")
async def index_vector(request: Request, project_id: str, push_request: PushRequest):
    project_model = await ProjectModel.create_instance(db_client=request.app.state.db)

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
    )

    has_records = True
    page_no = 1
    inserted_items_count = 0
    idx = 0

    chunk_model = await ChunkModel.create_instance(db_client=request.app.state.db)

    while has_records:
        page_chunks = await chunk_model.get_poject_chunks(
            project_id=project.id,
            page_no=page_no,
        )

        if len(page_chunks):
            page_no += 1
        
        if not page_chunks or len(page_chunks) == 0:
            has_records = False
            break

        chunks_ids =  list(range(idx, idx + len(page_chunks)))
        idx += len(page_chunks)
        
        reset_collection = bool(push_request.do_reset) and inserted_items_count == 0

        is_inserted = vec_controller.index_into_vector_db(
            project=project,
            chunks=page_chunks,
            do_reset=reset_collection,
            chunks_ids=chunks_ids,
        )

        if not is_inserted:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseSignal.INSERT_INTO_VECTORDB_ERROR.value
                }
            )
        
        inserted_items_count += len(page_chunks)
        
    return JSONResponse(
        content={
            "signal": ResponseSignal.INSERT_INTO_VECTORDB_SUCCESS.value,
            "inserted_items_count": inserted_items_count
        }
    )

@vectors_router.get("/index/info/{project_id}")
async def get_project_index_info(request: Request, project_id: str):
    
    project_model = await ProjectModel.create_instance(
        db_client=request.app.state.db
    )

    project = await project_model.get_project_or_create(
        project_id=project_id
    )

    vec_controller = VectorsController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
    )

    collection_info = vec_controller.get_vector_db_collection_info(project=project)

    return JSONResponse(
        content={
            "signal": ResponseSignal.VECTORDB_COLLECTION_RETRIEVED.value,
            "collection_info": collection_info
        }
    )

@vectors_router.post("/index/search/{project_id}")
async def search_index(request: Request, project_id: str, search_request: SearchRequest):
    
    project_model = await ProjectModel.create_instance(
        db_client=request.app.state.db
    )

    project = await project_model.get_project_or_create(
        project_id=project_id
    )

    vec_controller = VectorsController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    results = vec_controller.search_vector_db_collection(
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
            "results": [ result.dict()  for result in results ]
        }
    )

@vectors_router.post("/index/answer/{project_id}")
async def answer_rag(request: Request, project_id: str, search_request: SearchRequest):
    
    project_model = await ProjectModel.create_instance(
        db_client=request.app.state.db
    )

    project = await project_model.get_project_or_create(
        project_id=project_id
    )

    vec_controller = VectorsController(
        vector_db_client=request.app.vector_db_client,
        generation_client=request.app.generation_client,
        embedding_client=request.app.embedding_client,
        template_parser=request.app.template_parser,
    )

    answer, full_prompt, chat_history = vec_controller.answer_rag_question(
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