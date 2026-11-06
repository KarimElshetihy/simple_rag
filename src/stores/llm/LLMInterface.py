from abc import ABC, abstractmethod

class LLMInterface(ABC):

    @abstractmethod
    def set_generation_model(self, model_id: str):
        pass

    @abstractmethod
    def set_embedding_model(self, model_id: str, embedding_size: int):
        pass

    @abstractmethod
    async def generate_text(
        self, 
        prompt: str,
        chat_history: list | None = None,
        max_tokens: int = None,
        temperature: float = None,
        ):
        pass

    @abstractmethod
    async def embed_texts(
        self, texts: list[str], document_type: str = None
    ) -> list[list[float]] | None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

    @abstractmethod
    def construct_prompt(self, prompt: str, role: str):
        pass