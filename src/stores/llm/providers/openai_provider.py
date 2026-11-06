from src.enums.llm_enums import OpenAIEnums
from src.stores.llm.llm_interface import LLMInterface
from openai import AsyncOpenAI
import logging

class OpenAIProvider(LLMInterface):
    def __init__(self, 
                 api_key: str, 
                 api_url: str = None, 
                 input_max_characters: int = 1000, 
                 output_max_tokens: int = 1000,
                 temperature: float = 0.1
                 ):

        self.enums = OpenAIEnums
        self.api_key = api_key
        self.api_url = api_url
        self.input_max_characters = input_max_characters
        self.output_max_tokens = output_max_tokens
        self.temperature = temperature
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.api_url)
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
            await self.client.close()
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
            self.logger.error("OpenAI client was not set")
            return None

        if not self.generation_model_id:
            self.logger.error("Generation model for OpenAI was not set")
            return None

        max_tokens = max_tokens or self.output_max_tokens
        temperature = temperature or self.temperature

        messages = list(chat_history or [])
        messages.append(self.construct_prompt(prompt=prompt, role=OpenAIEnums.USER.value))


        response = await self.client.chat.completions.create(
            model=self.generation_model_id,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        if not response or not response.choices or not response.choices[0].message:
            self.logger.error("Error while generating text with OpenAI")
            return None

        return response.choices[0].message.content

    
    async def embed_texts(
        self, texts: list[str], document_type: str = None
    ) -> list[list[float]] | None:
        if not texts:
            return []
        if not self.client:
            self.logger.error("OpenAI client was not set")
            return None

        if not self.embedding_model_id:
            self.logger.error("Embedding model for OpenAI was not set")
            return None

        response = await self.client.embeddings.create(
            model=self.embedding_model_id,
            input=texts,
        )

        if not response or not response.data:
            self.logger.error("Error while embedding text with OpenAI")
            return None

        indexed_embeddings = sorted(response.data, key=lambda item: item.index)
        if [item.index for item in indexed_embeddings] != list(range(len(texts))):
            self.logger.error("OpenAI returned an incomplete embedding batch")
            return None
        vectors = [item.embedding for item in indexed_embeddings]
        if len(vectors) != len(texts) or any(not vector for vector in vectors):
            self.logger.error("OpenAI returned invalid embeddings for the batch")
            return None
        return vectors
    
    def construct_prompt(self, prompt: str, role: str):
        return {
            "role": role,
            "content": prompt
        }

    def process_text(self, text: str):
        return text[:self.input_max_characters].strip()