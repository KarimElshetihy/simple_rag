import logging
from dataclasses import dataclass
from time import perf_counter
from uuid import uuid4

from src.enums.llm_enums import DocumentTypeEnums
from src.enums import ResponseSignal
from src.infrastructure.database.repositories import (
    ChunkRepository,
    ProjectRepository,
)
from src.models.db_schemes.db_rag.schemes.project import Project
from src.models.db_schemes.db_rag.schemes.chunk import AssetChunk as Chunk


logger = logging.getLogger("uvicorn.error")


@dataclass
class VectorIndexResult:
    signal: ResponseSignal
    inserted_items_count: int = 0


class RagService:
    EMBEDDING_BATCH_SIZE = 64
    INDEX_PAGE_SIZE = 256
    VECTOR_UPSERT_BATCH_SIZE = 256

    def __init__(self, vector_db_client, generation_client, embedding_client, template_parser):
        self.vector_db_client = vector_db_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser

    def create_collection_name(self, project_id: str):
        return f"collection_{project_id}".strip()

    def create_staging_collection_name(self):
        return f"staging_{uuid4().hex}"

    async def index_project_chunks(
        self,
        project_id: str,
        project_repository: ProjectRepository,
        chunk_repository: ChunkRepository,
        do_reset: bool = False,
    ) -> VectorIndexResult:
        project = await project_repository.get_project_or_create(
            project_id=project_id
        )
        if not project:
            return VectorIndexResult(
                signal=ResponseSignal.PROJECT_NOT_FOUND_ERROR
            )

        staging_collection = (
            self.create_staging_collection_name() if do_reset else None
        )
        target_collection = staging_collection or self.create_collection_name(
            project_id=project.project_id
        )
        collection_published = False
        inserted_items_count = 0
        read_seconds = 0.0
        index_seconds = 0.0
        publish_seconds = 0.0

        try:
            page_no = 1
            while True:
                read_started = perf_counter()
                page_chunks = await chunk_repository.get_project_chunks(
                    project_id=project.id,
                    page_no=page_no,
                    page_size=self.INDEX_PAGE_SIZE,
                )
                read_seconds += perf_counter() - read_started
                # Release the chunk-table read lock before vector DB operations.
                await chunk_repository.session.commit()
                if not page_chunks:
                    break

                is_inserted = await self.index_into_vector_db(
                    project=project,
                    chunks=page_chunks,
                    collection_name=target_collection,
                )
                if not is_inserted:
                    return VectorIndexResult(
                        signal=ResponseSignal.INSERT_INTO_VECTORDB_ERROR
                    )

                inserted_items_count += len(page_chunks)
                page_no += 1

            if inserted_items_count:
                index_started = perf_counter()
                await self.ensure_vector_index(
                    project=project,
                    collection_name=target_collection,
                )
                index_seconds = perf_counter() - index_started
                if staging_collection:
                    publish_started = perf_counter()
                    await self.publish_staging_collection(
                        staging_collection=staging_collection,
                        project=project,
                    )
                    publish_seconds = perf_counter() - publish_started
                    collection_published = True

            logger.info(
                "Indexed %s chunks for project %s: chunk reads %.3fs, "
                "vector index build %.3fs, publish %.3fs.",
                inserted_items_count,
                project_id,
                read_seconds,
                index_seconds,
                publish_seconds,
            )
            return VectorIndexResult(
                signal=ResponseSignal.INSERT_INTO_VECTORDB_SUCCESS,
                inserted_items_count=inserted_items_count,
            )
        finally:
            if staging_collection and not collection_published:
                try:
                    await self.vector_db_client.delete_collection(
                        collection_name=staging_collection
                    )
                except Exception:
                    logger.exception(
                        "Failed to clean up staging vector collection %s",
                        staging_collection,
                    )

    async def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return await self.vector_db_client.delete_collection(
            collection_name=collection_name
        )

    async def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return await self.vector_db_client.get_collection_info(
            collection_name=collection_name
        )

    async def get_project_collection_info(
        self,
        project_id: str,
        project_repository: ProjectRepository,
    ):
        project = await project_repository.get_project_or_create(
            project_id=project_id
        )
        return await self.get_vector_db_collection_info(project=project)

    async def ensure_vector_index(
        self, project: Project, collection_name: str | None = None
    ):
        collection_name = collection_name or self.create_collection_name(
            project_id=project.project_id
        )
        return await self.vector_db_client.ensure_vector_index(
            collection_name=collection_name
        )

    async def publish_staging_collection(
        self, staging_collection: str, project: Project
    ):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return await self.vector_db_client.publish_staging_collection(
            staging_collection=staging_collection,
            collection_name=collection_name,
        )

    async def index_into_vector_db(
        self,
        project: Project,
        chunks: list[Chunk],
        collection_name: str | None = None,
    ) -> bool:
        collection_name = collection_name or self.create_collection_name(
            project_id=project.project_id
        )
        texts = [chunk.chunk_text for chunk in chunks]
        metadata = [chunk.chunk_metadata for chunk in chunks]
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        vectors = []
        embedding_started = perf_counter()
        for start in range(0, len(texts), self.EMBEDDING_BATCH_SIZE):
            batch_vectors = await self.embedding_client.embed_texts(
                texts=texts[start : start + self.EMBEDDING_BATCH_SIZE],
                document_type=DocumentTypeEnums.DOCUMENT.value,
            )
            expected_batch_size = min(
                self.EMBEDDING_BATCH_SIZE, len(texts) - start
            )
            if (
                batch_vectors is None
                or len(batch_vectors) != expected_batch_size
                or any(not vector for vector in batch_vectors)
            ):
                raise RuntimeError(
                    "Embedding provider failed to embed an indexed batch."
                )
            vectors.extend(batch_vectors)
        embedding_seconds = perf_counter() - embedding_started

        await self.vector_db_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
        )

        upsert_started = perf_counter()
        result = await self.vector_db_client.upsert_vectors(
            collection_name=collection_name,
            text_list=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunk_ids,
            chunk_ids=chunk_ids,
            batch_size=self.VECTOR_UPSERT_BATCH_SIZE,
        )
        logger.info(
            "Indexed vector batch of %s chunks for project %s: "
            "embedding %.3fs, database upsert %.3fs.",
            len(texts),
            project.project_id,
            embedding_seconds,
            perf_counter() - upsert_started,
        )
        return result

    async def search_vector_db_collection(
        self, project: Project, text: str, limit: int = 5
    ) -> list:

        collection_name = self.create_collection_name(project_id=project.project_id)
        vectors = await self.embedding_client.embed_texts(
            texts=[text],
            document_type=DocumentTypeEnums.QUERY.value,
        )

        if vectors is None or len(vectors) != 1 or not vectors[0]:
            return []

        return await self.vector_db_client.search_by_embedding(
            collection_name=collection_name,
            vector=vectors[0],
            limit=limit,
        )

    async def search_project(
        self,
        project_id: str,
        text: str,
        project_repository: ProjectRepository,
        limit: int = 5,
    ) -> list:
        project = await project_repository.get_project_or_create(
            project_id=project_id
        )
        return await self.search_vector_db_collection(
            project=project,
            text=text,
            limit=limit,
        )

    async def answer_rag_question(
        self, project: Project, query: str, limit: int = 5
    ) -> tuple[str | None, str | None, list | None]:
        
        answer, full_prompt, chat_history = None, None, None

        retrieved_documents = await self.search_vector_db_collection(
            project=project,
            text=query,
            limit=limit,
        )

        if not retrieved_documents or len(retrieved_documents) == 0:
            return answer, full_prompt, chat_history

        system_prompt = self.template_parser.get("rag", "system_prompt")

        documents_prompts = "\n".join(
            [
                self.template_parser.get(
                    "rag",
                    "document_prompt",
                    {
                        "doc_num": idx + 1,
                        "chunk_text": self.generation_client.process_text(doc.text),
                    },
                )
                for idx, doc in enumerate(retrieved_documents)
            ]
        )

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {"query": query})

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enums.SYSTEM.value,
            )
        ]

        full_prompt = "\n\n".join([ documents_prompts,  footer_prompt])

        answer = await self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )

        return answer, full_prompt, chat_history

    async def answer_project_question(
        self,
        project_id: str,
        query: str,
        project_repository: ProjectRepository,
        limit: int = 5,
    ) -> tuple[str | None, str | None, list | None]:
        project = await project_repository.get_project_or_create(
            project_id=project_id
        )
        return await self.answer_rag_question(
            project=project,
            query=query,
            limit=limit,
        )

    