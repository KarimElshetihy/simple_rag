from src.enums.vector_db_enums import VectorDBEnums
from src.helpers.config import Settings
from .providers.qdrant_db import QdrantDB
from .providers.pgvector_provider import PGVectorDBProvider
from src.infrastructure.filesystem import StoragePaths

class VectorDBProviderFactory:
    def __init__(self, config: Settings):
        self.config = config
        self.storage_paths = StoragePaths()
        
    def create(self, provider: str | None):
        if provider == VectorDBEnums.QDRANT.value:
            db_path = self.storage_paths.get_vector_db_path(
                db_name=self.config.VECTOR_DB_PATH
            )
            return QdrantDB(
                db_path=db_path,
                distance_method=self.config.VECTOR_DB_DISTANCE_METRIC,
            )
        if provider == VectorDBEnums.PGVECTOR.value:
            if not self.config.POSTGRES_URI:
                raise ValueError("POSTGRES_URI must be configured for pgvector.")
            return PGVectorDBProvider(
                db_path=self.config.POSTGRES_URI,
                distance_method=self.config.VECTOR_DB_DISTANCE_METRIC,
                embedding_size=self.config.EMBEDDING_MODEL_SIZE,
                index_type=getattr(
                    self.config, "PGVECTOR_INDEX_TYPE", "hnsw"
                ),
            )
        return None