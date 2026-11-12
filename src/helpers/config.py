from typing import Literal
from urllib.parse import quote

from pydantic import SecretStr
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

    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_DEFAULT_USER: str = "guest"
    RABBITMQ_DEFAULT_PASS: SecretStr = SecretStr("guest")

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
    OCR_LANGUAGES: str = "eng+ara"
    TESSERACT_CMD: str | None = None
    TESSDATA_DIR: str | None = None

    PRIMARY_LANG: str = "en"
    DEFAULT_LANG: str = "en"

    @property
    def celery_broker_url(self) -> str:
        username = quote(self.RABBITMQ_DEFAULT_USER, safe="")
        password = quote(
            self.RABBITMQ_DEFAULT_PASS.get_secret_value(),
            safe="",
        )
        return (
            f"amqp://{username}:{password}@"
            f"{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}//"
        )


def get_settings() -> Settings:
    return Settings()
