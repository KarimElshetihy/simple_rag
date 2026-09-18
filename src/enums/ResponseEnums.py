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