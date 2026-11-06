from enum import Enum

class ResponseSignal(Enum):

    FILE_VALIDATED_SUCCESS = "✅ file_validated_successfully"
    FILE_TYPE_NOT_SUPPORTED = "❌ file_type_not_supported"
    FILE_SIZE_EXCEEDED = "❌ file_size_exceeded_limit"
    FILE_UPLOAD_SUCCESS = "✅ file_uploaded_successfully"
    FILE_UPLOAD_FAILED = "❌ file_upload_failed"
    PROCESSING_SUCCESS = "✅ file_processed_successfully"
    PROCESSING_FAILED = "❌ file_processing_failed"
    NO_PROJECT_FILES_ERROR = "❌ No files found for this project"
    FILE_ERROR = "❌ No file found for this id"
    PROJECT_NOT_FOUND_ERROR = "project_not_found"
    INSERT_INTO_VECTORDB_ERROR = "insert_into_vectordb_error"
    INSERT_INTO_VECTORDB_SUCCESS = "insert_into_vectordb_success"
    VECTORDB_COLLECTION_RETRIEVED = "vectordb_collection_retrieved"
    VECTORDB_SEARCH_ERROR = "vectordb_search_error"
    VECTORDB_SEARCH_SUCCESS = "vectordb_search_success"
    RAG_ANSWER_ERROR = "rag_answer_error"
    RAG_ANSWER_SUCCESS = "rag_answer_success"