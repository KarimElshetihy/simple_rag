from enum import Enum

class VectorDBEnums(Enum):
    QDRANT = "QDRANT"
    PGVECTOR = "PGVECTOR"

class DistanceMethodEnums(Enum):
    COSINE = "cosine"
    DOT = "dot"

class PGVectorSchemaEnums(Enum):
    ID = "id"
    VECTOR = "vector"
    METADATA = "metadata"
    TEXT = "text"
    CHUNK_ID = "chunk_id"
    _PREFIX = "vec"

class PGVectorDistanceMethodEnums(Enum):
    COSINE = "vector_cosine_ops"
    DOT = "vector_ip_ops"

class PGVectorIndexTypeEnums(Enum):
    IVFFLAT = "ivfflat"
    HNSW = "hnsw"