from src.enums.LLMEnums import CoHereEnums, DocumentTypeEnums
from src.stores.llm.LLMInterface import LLMInterface
import cohere
import logging

class CoHereProvider(LLMInterface):
    def __init__(self, 
                 api_key: str, 
                 input_max_characters: int = 1000, 
                 output_max_tokens: int = 1000,
                 temperature: float = 0.1
                 ):

        self.enums = CoHereEnums
        self.api_key = api_key
        self.input_max_characters = input_max_characters
        self.output_max_tokens = output_max_tokens
        self.temperature = temperature
        self.client = cohere.AsyncClient(api_key=self.api_key)
        # self.generation_model = "gpt-4"
        # self.embedding_model = "text-embedding-3-small"

        self.generation_model_id = None
        self.embedding_model_id = None
        self.embedding_size = None
        self.generation_model_id = None

        self.logger = logging.getLogger(__name__)

    def set_generation_model(self, model_id: str):
        self.generation_model_id = model_id   

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    async def close(self) -> None:
        if self.client is not None:
            await self.client.__aexit__(None, None, None)
            self.client = None

    
    async def generate_text(
        self, 
        prompt: str,
        chat_history: list = None,
        max_tokens: int = None,
        temperature: float = None,
        # **kwargs
        ):
        if not self.client:
            self.logger.error("CoHere client was not set")
            return None

        if not self.generation_model_id:
            self.logger.error("Generation model for CoHere was not set")
            return None

        max_tokens = max_tokens or self.output_max_tokens
        temperature = temperature or self.temperature

        response = await self.client.chat(
            model=self.generation_model_id,
            chat_history=chat_history or [],
            message=self.process_text(prompt),
            max_tokens=max_tokens,
            temperature=temperature
        )

        if not response or not response.text:
            self.logger.error("Error while generating text with CoHere")
            return None
        return response.text

    
    async def embed_text(self, text: str, document_type: str = None):
        if not self.client:
            self.logger.error("CoHere client was not set")
            return None

        if not self.embedding_model_id:
            self.logger.error("Embedding model for CoHere was not set")
            return None

        if document_type == DocumentTypeEnums.QUERY.value:
            input_type = CoHereEnums.QUERY.value
        else:
            input_type = CoHereEnums.DOCUMENT.value


        response = await self.client.embed(
            model=self.embedding_model_id,
            texts=[self.process_text(text)],
            input_type=input_type,
            embedding_types=["float"]
        )

        if not response or not response.embeddings or not response.embeddings.float_:
            self.logger.error("Error while embedding text with CoHere")
            return None

        return response.embeddings.float_[0]
    
    def construct_prompt(self, prompt: str, role: str):
        return {
            "role": role,
            "text": prompt
        }

    def process_text(self, text: str):
        return text[:self.input_max_characters].strip()