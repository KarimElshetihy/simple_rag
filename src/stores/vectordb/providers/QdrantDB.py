import logging
from hashlib import sha256
from uuid import uuid4

from qdrant_client import AsyncQdrantClient, models

from ..VectorDBInterface import VectorDBInterface
from src.enums.VectorDBEnums import DistanceMethodEnums
from src.models.db_schemes.chunk import RetrievedDocument


class QdrantDB(VectorDBInterface):
    supports_chunk_ids = False

    def __init__(self, db_path: str, distance_method: str):
        self.client: AsyncQdrantClient | None = None
        self.db_path = db_path
        self.distance_method = (
            models.Distance.COSINE
            if distance_method == DistanceMethodEnums.COSINE.value
            else models.Distance.DOT
        )
        self.logger = logging.getLogger(__name__)

    def _require_client(self) -> AsyncQdrantClient:
        if self.client is None:
            raise RuntimeError("The Qdrant provider is not connected.")
        return self.client

    @staticmethod
    def _active_alias_name(collection_name: str) -> str:
        return f"active_{sha256(collection_name.encode()).hexdigest()}"

    async def _get_active_alias_target(self, collection_name: str) -> str | None:
        alias_name = self._active_alias_name(collection_name)
        aliases = await self._require_client().get_aliases()
        for alias in aliases.aliases:
            if alias.alias_name == alias_name:
                return alias.collection_name
        return None

    async def _collection_reference(self, collection_name: str) -> str:
        if await self._get_active_alias_target(collection_name):
            return self._active_alias_name(collection_name)
        return collection_name

    async def connect(self) -> None:
        self.client = AsyncQdrantClient(path=self.db_path)
        self.logger.info("Connected to Qdrant at %s", self.db_path)

    async def disconnect(self) -> None:
        if self.client is not None:
            await self.client.close()
            self.client = None
            self.logger.info("Disconnected from Qdrant at %s", self.db_path)

    async def is_collection_exist(self, collection_name: str) -> bool:
        return (
            await self._get_active_alias_target(collection_name) is not None
            or await self._require_client().collection_exists(
                collection_name=collection_name
            )
        )

    async def list_all_collections(self) -> list[str]:
        collections = await self._require_client().get_collections()
        return [collection.name for collection in collections.collections]

    async def get_collection_info(self, collection_name: str) -> dict:
        collection_reference = await self._collection_reference(collection_name)
        info = await self._require_client().get_collection(
            collection_name=collection_reference
        )
        return info.model_dump()

    async def delete_collection(self, collection_name: str) -> None:
        client = self._require_client()
        alias_name = self._active_alias_name(collection_name)
        active_target = await self._get_active_alias_target(collection_name)
        if active_target is not None:
            await client.update_collection_aliases(
                change_aliases_operations=[
                    models.DeleteAliasOperation(
                        delete_alias=models.DeleteAlias(alias_name=alias_name)
                    )
                ]
            )
            await client.delete_collection(collection_name=active_target)
        if await client.collection_exists(collection_name=collection_name):
            await client.delete_collection(collection_name=collection_name)

    async def ensure_vector_index(self, collection_name: str) -> bool:
        if not await self.is_collection_exist(collection_name):
            raise ValueError(f"Collection does not exist: {collection_name}")
        return False

    async def publish_collection(
        self, staging_collection: str, collection_name: str
    ) -> None:
        if staging_collection == collection_name:
            raise ValueError("The staging and published collection names must differ.")

        client = self._require_client()
        if not await client.collection_exists(collection_name=staging_collection):
            raise ValueError(f"Staging collection does not exist: {staging_collection}")

        alias_name = self._active_alias_name(collection_name)
        previous_target = await self._get_active_alias_target(collection_name)
        operations = []
        if previous_target is not None:
            operations.append(
                models.DeleteAliasOperation(
                    delete_alias=models.DeleteAlias(alias_name=alias_name)
                )
            )
        operations.append(
            models.CreateAliasOperation(
                create_alias=models.CreateAlias(
                    collection_name=staging_collection,
                    alias_name=alias_name,
                )
            )
        )
        await client.update_collection_aliases(
            change_aliases_operations=operations
        )

        retired_collections = {previous_target, collection_name} - {
            None,
            staging_collection,
        }
        for retired_collection in retired_collections:
            try:
                if await client.collection_exists(collection_name=retired_collection):
                    await client.delete_collection(collection_name=retired_collection)
            except Exception:
                self.logger.exception(
                    "Published collection %s, but failed to remove old collection %s.",
                    collection_name,
                    retired_collection,
                )

        self.logger.info(
            "Published staging collection %s as %s.",
            staging_collection,
            collection_name,
        )

    async def create_collection(
        self, collection_name: str, embedding_size: int, do_reset: bool = False
    ) -> bool:
        if embedding_size <= 0:
            raise ValueError("Embedding size must be greater than zero.")
        if do_reset:
            await self.delete_collection(collection_name)

        if not await self.is_collection_exist(collection_name):
            await self._require_client().create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size,
                    distance=self.distance_method,
                ),
            )
            self.logger.info("Collection %s created.", collection_name)
            return True
        return False

    async def insert_vector(
        self,
        collection_name: str,
        text: str,
        vector: list[float],
        metadata: dict | None = None,
        record_id: str | int | None = None,
        chunk_id: int | None = None,
    ) -> bool:
        return await self.insert_many_vectors(
            collection_name=collection_name,
            text_list=[text],
            vectors=[vector],
            metadata=[metadata],
            record_ids=[record_id],
            chunk_ids=[chunk_id],
        )

    async def insert_many_vectors(
        self,
        collection_name: str,
        text_list: list[str],
        vectors: list[list[float]],
        metadata: list[dict | None] | None = None,
        record_ids: list[str | int | None] | None = None,
        batch_size: int = 50,
        chunk_ids: list[int | None] | None = None,
    ) -> bool:
        if len(text_list) != len(vectors):
            raise ValueError("Text and vector counts must match.")
        if batch_size <= 0:
            raise ValueError("Batch size must be greater than zero.")
        if metadata is None:
            metadata = [None] * len(text_list)
        if record_ids is None:
            record_ids = [None] * len(text_list)
        if chunk_ids is None:
            chunk_ids = (
                [
                    record_id
                    if isinstance(record_id, int) and not isinstance(record_id, bool)
                    else None
                    for record_id in record_ids
                ]
                if record_ids is not None
                else [None] * len(text_list)
            )
        if any(
            len(values) != len(text_list)
            for values in (metadata, record_ids, chunk_ids)
        ):
            raise ValueError(
                "Text, metadata, record ID, and chunk ID counts must match."
            )
        if not await self.is_collection_exist(collection_name):
            self.logger.error(
                "Cannot insert records into non-existent collection: %s",
                collection_name,
            )
            return False

        points = [
            models.PointStruct(
                id=record_ids[index] or str(uuid4()),
                vector=vector,
                payload={
                    "text": text_list[index],
                    "metadata": metadata[index] or {},
                    "chunk_id": chunk_ids[index],
                },
            )
            for index, vector in enumerate(vectors)
        ]
        client = self._require_client()
        collection_reference = await self._collection_reference(collection_name)
        for start in range(0, len(points), batch_size):
            await client.upsert(
                collection_name=collection_reference,
                points=points[start : start + batch_size],
            )
        return True

    async def search_by_vector(
        self, collection_name: str, vector: list[float], limit: int = 5
    ) -> list[RetrievedDocument]:
        if limit <= 0:
            raise ValueError("Search limit must be greater than zero.")
        collection_reference = await self._collection_reference(collection_name)
        results = await self._require_client().query_points(
            collection_name=collection_reference,
            query=vector,
            limit=limit,
            with_payload=True,
        )
        if not results.points:
            self.logger.warning(
                "No results found for the given vector in collection: %s",
                collection_name,
            )
            return []

        documents = []
        for point in results.points:
            payload = point.payload or {}
            documents.append(
                RetrievedDocument(
                    text=payload.get("text", ""),
                    score=point.score,
                    chunk_id=payload.get("chunk_id"),
                )
            )
        return documents
