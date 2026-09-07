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

    class Config:
        env_file = "src/.env"


def get_settings():
    return Settings()
