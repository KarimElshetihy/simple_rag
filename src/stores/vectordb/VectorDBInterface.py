from abc import ABC, abstractmethod

from src.models.db_schemes.chunk import RetrievedDocument


class VectorDBInterface(ABC):
    """Asynchronous contract shared by vector database providers."""

    @abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def is_collection_exist(self, collection_name: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def list_all_collections(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    async def get_collection_info(self, collection_name: str) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def delete_collection(self, collection_name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def create_collection(
        self,
        collection_name: str,
        embedding_size: int,
        do_reset: bool = False,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def insert_vector(
        self,
        collection_name: str,
        text: str,
        vector: list[float],
        metadata: dict | None = None,
        record_id: str | int | None = None,
        **provider_options,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def insert_many_vectors(
        self,
        collection_name: str,
        text_list: list[str],
        vectors: list[list[float]],
        metadata: list[dict | None] | None = None,
        record_ids: list[str | int | None] | None = None,
        batch_size: int = 50,
        **provider_options,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def search_by_vector(
        self,
        collection_name: str,
        vector: list[float],
        limit: int = 5,
    ) -> list[RetrievedDocument]:
        raise NotImplementedError

    async def ensure_vector_index(self, collection_name: str) -> bool:
        return False
