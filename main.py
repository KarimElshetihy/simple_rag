from fastapi import FastAPI
from src.routes import base, data, vectors
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
from src.helpers.config import get_settings
from src.stores.llm.LLMProviderFactory import LLMProviderFactory
from src.stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from src.stores.llm.templates.template_parser import TemplateParser

# ------------ LIFESPAN EVENT HANDLER ------------ #
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. On Startup: Initialize the Motor client
    settings = get_settings()
    app.state.mongo_client = AsyncIOMotorClient(settings.MONGODB_URI)
    app.state.db = app.state.mongo_client[settings.MONGODB_DB_NAME]
    llm_factory = LLMProviderFactory(settings)
    vector_db_factory = VectorDBProviderFactory(settings)

    # Generation client
    app.generation_client = llm_factory.create(provider=settings.GENERATION_BACKEND) 
    app.generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID)

    # Embedding client
    app.embedding_client = llm_factory.create(provider=settings.EMBEDDING_BACKEND)
    app.embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID, embedding_size=settings.EMBEDDING_MODEL_SIZE)

    # Vector store client
    app.vector_db_client = vector_db_factory.create(provider=settings.VECTOR_DB_BACKEND)
    app.vector_db_client.connect()

    app.template_parser = TemplateParser(
        language=settings.PRIMARY_LANG,
        default_language=settings.DEFAULT_LANG,
    )

    # Optional: Analogous to "create_all", you can build indexes here on startup
    # await app.state.db["users"].create_index([("email", 1)], unique=True)

    yield

    # 2. On Shutdown: Close the Motor client connection cleanly
    app.state.mongo_client.close()
    app.vector_db_client.disconnect()


app = FastAPI(lifespan=lifespan)
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(vectors.vectors_router)
