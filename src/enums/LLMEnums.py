from enum import Enum

class LLMEnums(Enum):
    OPENAI = "OPENAI"
    COHERE = "COHERE"

class OpenAIEnums(Enum):
    SYSTEM = "system"
    ASSISTANT = "assistant"
    USER = "user"

class CoHereEnums(Enum):
    SYSTEM = "SYSTEM"
    ASSISTANT = "CHATBOT"
    USER = "USER"
    DOCUMENT = "search_document"
    QUERY = "search_query"

class DocmentTypeEnums(Enum):
    DOCUMENT = "document"
    QUERY = "query"