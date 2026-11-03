from enum import Enum

class BackendDBEnum(Enum):
    POSTGRES = "postgres"
    MONGODB = "mongodb"

class DatabaseEnum(Enum):
    COLLECTION_PROJECT_NAME = "projects"
    COLLECTION_CHUNK_NAME = "chunks"
    COLLECTION_ASSET_NAME = "assets"
