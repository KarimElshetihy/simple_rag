from enums.LLMEnums import CoHereEnums, DocmentTypeEnums
from llm.LLMInterface import LLMInterface
import cohere
import logging

class CoHereProvider(LLMInterface):
    def __init__(self, 
                 api_key: str, 
                 input_max_characters: int = 1000, 
                 output_max_tokens: int = 1000,
                 temperature: float = 0.1
                 ):
        
        self.api_key = api_key
        self.input_max_characters = input_max_characters
        self.output_max_tokens = output_max_tokens
        self.temperature = temperature
        self.client = cohere.Client(api_key=self.api_key)
        # self.generation_model = "gpt-4"
        # self.embedding_model = "text-embedding-3-small"

        self.generation_model_id = None
        self.embedding_model_id = None
        self.embedding_size = None
        self.generation_model_id = None

        self.logger = logging.getLogger(__name__)

    def set_generation_model(self, model_id: str):
        self.generation_model = model_id    

    def set_embedding_model(self, model_id: str, embedding_size: int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size

    
    def generate_text(
        self, 
        prompt: str,
        chat_history: list=[],
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

        chat_history.append(self.construct_prompt(prompt=prompt, role=CoHereEnums.USER.value))

        response = self.client.chat(
            model=self.generation_model_id,
            chat_history=chat_history,
            message=self.process_text(prompt),
            max_tokens=max_tokens,
            temperature=temperature
        )

        if not response or not response.text:
            self.logger.error("Error while generating text with CoHere")
            return None
        return response.text

    
    def embed_text(self, text: str, document_type: str = None):
        if not self.client:
            self.logger.error("CoHere client was not set")
            return None

        if not self.embedding_model_id:
            self.logger.error("Embedding model for CoHere was not set")
            return None

        if document_type == DocmentTypeEnums.QUERY.value:
            input_type = CoHereEnums.QUERY.value
        input_type = CoHereEnums.DOCUMENT.value


        response = self.client.embed(
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
            "text": self.process_text(prompt)
        }

    def process_text(self, text: str):
        return text[:self.input_max_characters].strip()