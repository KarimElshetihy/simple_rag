from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.enums.Database_Enums import BackendDBEnum
from src.helpers.config import get_settings
from src.routes import base, data, vectors
from src.stores.llm.LLMProviderFactory import LLMProviderFactory
from src.stores.llm.templates.template_parser import TemplateParser
from src.stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    if settings.DATABASE_BACKEND != BackendDBEnum.POSTGRES:
        raise ValueError(
            f"{settings.DATABASE_BACKEND.value} is not configured; "
            "this application currently supports PostgreSQL only."
        )
    if not settings.POSTGRES_URI:
        raise ValueError("POSTGRES_URI must be configured for PostgreSQL.")

    async with AsyncExitStack() as exit_stack:
        app.state.db_engine = create_async_engine(settings.POSTGRES_URI)
        exit_stack.push_async_callback(app.state.db_engine.dispose)
        app.state.session_factory = async_sessionmaker(
            app.state.db_engine,
            expire_on_commit=False,
        )

        llm_factory = LLMProviderFactory(settings)
        vector_db_factory = VectorDBProviderFactory(settings)

        app.generation_client = llm_factory.create(
            provider=settings.GENERATION_BACKEND
        )
        if app.generation_client is None:
            raise ValueError(
                f"Unsupported generation provider: {settings.GENERATION_BACKEND}"
            )
        exit_stack.push_async_callback(app.generation_client.close)
        app.generation_client.set_generation_model(
            model_id=settings.GENERATION_MODEL_ID
        )

        app.embedding_client = llm_factory.create(
            provider=settings.EMBEDDING_BACKEND
        )
        if app.embedding_client is None:
            raise ValueError(
                f"Unsupported embedding provider: {settings.EMBEDDING_BACKEND}"
            )
        exit_stack.push_async_callback(app.embedding_client.close)
        app.embedding_client.set_embedding_model(
            model_id=settings.EMBEDDING_MODEL_ID,
            embedding_size=settings.EMBEDDING_MODEL_SIZE,
        )

        app.vector_db_client = vector_db_factory.create(
            provider=settings.VECTOR_DB_BACKEND
        )
        if app.vector_db_client is None:
            raise ValueError(
                f"Unsupported vector database provider: {settings.VECTOR_DB_BACKEND}"
            )
        exit_stack.push_async_callback(app.vector_db_client.disconnect)
        await app.vector_db_client.connect()

        app.template_parser = TemplateParser(
            language=settings.PRIMARY_LANG,
            default_language=settings.DEFAULT_LANG,
        )

        yield


app = FastAPI(lifespan=lifespan)
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(vectors.vectors_router)
