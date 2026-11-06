from pydantic_settings import BaseSettings, SettingsConfigDict
from ..enums.Database_Enums import BackendDBEnum
from ..enums.VectorDBEnums import PGVectorIndexTypeEnums
from typing import List

class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    OPENAI_API_KEY: str

    FILE_SUPPORTED_TYPES: list
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE: int

    DATABASE_BACKEND: BackendDBEnum = BackendDBEnum.POSTGRES
    MONGODB_URI: str | None = None
    MONGODB_DB_NAME: str | None = None

    MONGO_INITDB_ROOT_USERNAME: str | None = None
    MONGO_INITDB_ROOT_PASSWORD: str | None = None

    POSTGRES_URI: str | None = None
    POSTGRES_HOST: str | None = None
    POSTGRES_PORT: int | None = None
    POSTGRES_DB_NAME: str | None = None
    POSTGRES_USER: str | None = None
    POSTGRES_PASSWORD: str | None = None

    # ===================== LLM Configs ===================== #
    GENERATION_BACKEND: str
    EMBEDDING_BACKEND: str

    OPENAI_API_KEY: str = None
    OPENAI_API_URL: str = None
    COHERE_API_KEY: str = None

    GENERATION_MODEL_ID: str = None
    EMBEDDING_MODEL_ID: str = None
    EMBEDDING_MODEL_SIZE: int = None

    INPUT_MAX_CHARACTERS: int = None
    OUTPUT_MAX_TOKENS: int = None
    TEMPERATURE: float = None

    VECTOR_DB_BACKEND_LITERAL: List[str] = None
    VECTOR_DB_BACKEND: str = None
    VECTOR_DB_PATH: str = None
    VECTOR_DB_DISTANCE_METRIC: str = None
    PGVECTOR_INDEX_TYPE: str = PGVectorIndexTypeEnums.HNSW.value

    PRIMARY_LANG: str = "en"
    DEFAULT_LANG: str = "en"

    class Config:
        env_file = "src/.env"


def get_settings():
    return Settings()
