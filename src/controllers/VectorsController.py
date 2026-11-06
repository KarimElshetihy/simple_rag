import asyncio
from uuid import uuid4

from .BaseController import BaseController
from ..enums.LLMEnums import DocumentTypeEnums
from ..models.db_schemes.db_rag.schemes.project import Project
from ..models.db_schemes.db_rag.schemes.chunk import AssetChunk as Chunk

class VectorsController(BaseController):
    def __init__(self, vector_db_client, generation_client, embedding_client, template_parser):
        super().__init__()

        self.vector_db_client = vector_db_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser

    def create_collection_name(self, project_id: str):
        return f"collection_{project_id}".strip()

    def create_staging_collection_name(self):
        return f"staging_{uuid4().hex}"

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

    async def ensure_vector_index(
        self, project: Project, collection_name: str | None = None
    ):
        collection_name = collection_name or self.create_collection_name(
            project_id=project.project_id
        )
        return await self.vector_db_client.ensure_vector_index(
            collection_name=collection_name
        )

    async def publish_vector_collection(
        self, staging_collection: str, project: Project
    ):
        collection_name = self.create_collection_name(project_id=project.project_id)
        return await self.vector_db_client.publish_collection(
            staging_collection=staging_collection,
            collection_name=collection_name,
        )

    async def index_into_vector_db(
        self,
        project: Project,
        chunks: list[Chunk],
        do_reset: bool = False,
        collection_name: str | None = None,
    ) -> bool:
        collection_name = collection_name or self.create_collection_name(
            project_id=project.project_id
        )
        texts = [chunk.chunk_text for chunk in chunks]
        metadata = [chunk.chunk_metadata for chunk in chunks]
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        vectors = await asyncio.gather(
            *(
                self.embedding_client.embed_text(
                    text=text,
                    document_type=DocumentTypeEnums.DOCUMENT.value,
                )
                for text in texts
            )
        )
        if any(vector is None for vector in vectors):
            raise RuntimeError("Embedding provider failed to embed an indexed chunk.")

        await self.vector_db_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )

        return await self.vector_db_client.insert_many_vectors(
            collection_name=collection_name,
            text_list=texts,
            metadata=metadata,
            vectors=vectors,
            record_ids=chunk_ids,
            chunk_ids=chunk_ids,
        )

    async def search_vector_db_collection(
        self, project: Project, text: str, limit: int = 10
    ) -> list:

        collection_name = self.create_collection_name(project_id=project.project_id)
        vector = await self.embedding_client.embed_text(
            text=text,
            document_type=DocumentTypeEnums.QUERY.value,
        )

        if not vector or len(vector) == 0:
            return []

        return await self.vector_db_client.search_by_vector(
            collection_name=collection_name,
            vector=vector,
            limit=limit,
        )
    
    async def answer_rag_question(
        self, project: Project, query: str, limit: int = 10
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

    