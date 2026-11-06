from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from ..enums.database_enums import BackendDBEnum
from ..enums.vector_db_enums import PGVectorIndexTypeEnums


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="src/.env", extra="ignore")

    APP_NAME: str
    APP_VERSION: str

    FILE_SUPPORTED_TYPES: list[str]
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE: int

    DATABASE_BACKEND: BackendDBEnum = BackendDBEnum.POSTGRES
    POSTGRES_URI: str | None = None

    GENERATION_BACKEND: Literal["OPENAI", "COHERE"]
    EMBEDDING_BACKEND: Literal["OPENAI", "COHERE"]

    OPENAI_API_KEY: str | None = None
    OPENAI_API_URL: str | None = None
    COHERE_API_KEY: str | None = None

    GENERATION_MODEL_ID: str | None = None
    EMBEDDING_MODEL_ID: str | None = None
    EMBEDDING_MODEL_SIZE: int | None = None

    INPUT_MAX_CHARACTERS: int | None = None
    OUTPUT_MAX_TOKENS: int | None = None
    TEMPERATURE: float | None = None

    VECTOR_DB_BACKEND: Literal["QDRANT", "PGVECTOR"] | None = None
    VECTOR_DB_PATH: str | None = None
    VECTOR_DB_DISTANCE_METRIC: Literal["cosine", "dot"] | None = None
    PGVECTOR_INDEX_TYPE: Literal["hnsw", "ivfflat"] = (
        PGVectorIndexTypeEnums.HNSW.value
    )
    DATA_DIR: str = "data"

    PRIMARY_LANG: str = "en"
    DEFAULT_LANG: str = "en"


def get_settings() -> Settings:
    return Settings()
