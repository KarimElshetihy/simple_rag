from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    APP_VERSION: str
    OPENAI_API_KEY: str

    FILE_SUPPORTED_TYPES: list
    FILE_MAX_SIZE: int
    FILE_DEFAULT_CHUNK_SIZE: int

    MONGODB_URI: str
    MONGODB_DB_NAME: str

    MONGO_INITDB_ROOT_USERNAME: str
    MONGO_INITDB_ROOT_PASSWORD: str

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

    VECTOR_DB_BACKEND: str = None
    VECTOR_DB_PATH: str = None
    VECTOR_DB_DISTANCE_METRIC: str = None

    class Config:
        env_file = "src/.env"


def get_settings():
    return Settings()
