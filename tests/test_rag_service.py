import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from src.application.services.rag_service import RagService


class FakeEmbeddingClient:
    embedding_size = 3

    def __init__(self, results=None):
        self.results = results
        self.calls = []

    async def embed_texts(self, texts, document_type):
        self.calls.append((texts, document_type))
        if self.results is not None:
            return self.results.pop(0)
        return [[float(index)] for index, _ in enumerate(texts)]


class RagServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.embedding_client = FakeEmbeddingClient()
        self.vector_db_client = SimpleNamespace(
            create_collection=AsyncMock(return_value=True),
            upsert_vectors=AsyncMock(return_value=True),
            search_by_embedding=AsyncMock(return_value=["result"]),
        )
        self.project = SimpleNamespace(project_id="project-1")
        self.controller = RagService(
            vector_db_client=self.vector_db_client,
            generation_client=SimpleNamespace(),
            embedding_client=self.embedding_client,
            template_parser=SimpleNamespace(),
        )

    async def test_index_batches_embeddings_and_upserts_aligned_chunk_data(self):
        chunks = [
            SimpleNamespace(
                chunk_text=f"text-{index}",
                chunk_metadata={"index": index},
                chunk_id=index + 1,
            )
            for index in range(65)
        ]

        result = await self.controller.index_into_vector_db(
            project=self.project,
            chunks=chunks,
        )

        self.assertTrue(result)
        self.assertEqual(
            [len(call[0]) for call in self.embedding_client.calls],
            [64, 1],
        )
        self.vector_db_client.create_collection.assert_awaited_once_with(
            collection_name="collection_project-1",
            embedding_size=3,
        )
        self.vector_db_client.upsert_vectors.assert_awaited_once()
        upsert_kwargs = self.vector_db_client.upsert_vectors.await_args.kwargs
        self.assertEqual(upsert_kwargs["text_list"], [chunk.chunk_text for chunk in chunks])
        self.assertEqual(upsert_kwargs["chunk_ids"], [chunk.chunk_id for chunk in chunks])
        self.assertEqual(len(upsert_kwargs["vectors"]), len(chunks))

    async def test_index_rejects_incomplete_embedding_batch_before_writing(self):
        self.embedding_client.results = [[[1.0]]]
        chunks = [
            SimpleNamespace(
                chunk_text="first",
                chunk_metadata={},
                chunk_id=1,
            ),
            SimpleNamespace(
                chunk_text="second",
                chunk_metadata={},
                chunk_id=2,
            ),
        ]

        with self.assertRaisesRegex(RuntimeError, "failed to embed"):
            await self.controller.index_into_vector_db(
                project=self.project,
                chunks=chunks,
            )

        self.vector_db_client.create_collection.assert_not_awaited()
        self.vector_db_client.upsert_vectors.assert_not_awaited()

    async def test_search_embeds_single_query_and_searches_by_embedding(self):
        results = await self.controller.search_vector_db_collection(
            project=self.project,
            text="question",
            limit=3,
        )

        self.assertEqual(results, ["result"])
        self.assertEqual(self.embedding_client.calls, [(["question"], "query")])
        self.vector_db_client.search_by_embedding.assert_awaited_once_with(
            collection_name="collection_project-1",
            vector=[0.0],
            limit=3,
        )

    async def test_search_skips_provider_when_query_embedding_is_empty(self):
        self.embedding_client.results = [[]]

        results = await self.controller.search_vector_db_collection(
            project=self.project,
            text="question",
        )

        self.assertEqual(results, [])
        self.vector_db_client.search_by_embedding.assert_not_awaited()

    async def test_project_index_pages_chunks_then_publishes_staging_collection(self):
        project = SimpleNamespace(id=9, project_id="project-1")
        project_repository = SimpleNamespace(
            get_project_or_create=AsyncMock(return_value=project)
        )
        first_page = [SimpleNamespace(chunk_id=1), SimpleNamespace(chunk_id=2)]
        chunk_repository = SimpleNamespace(
            get_project_chunks=AsyncMock(side_effect=[first_page, []])
        )
        self.controller.index_into_vector_db = AsyncMock(return_value=True)
        self.controller.ensure_vector_index = AsyncMock(return_value=True)
        self.controller.publish_staging_collection = AsyncMock()
        self.controller.create_staging_collection_name = lambda: "staging-test"
        self.vector_db_client.delete_collection = AsyncMock()

        result = await self.controller.index_project_chunks(
            project_id="project-1",
            project_repository=project_repository,
            chunk_repository=chunk_repository,
            do_reset=True,
        )

        from src.enums import ResponseSignal

        self.assertEqual(result.signal, ResponseSignal.INSERT_INTO_VECTORDB_SUCCESS)
        self.assertEqual(result.inserted_items_count, 2)
        self.assertEqual(
            [call.kwargs["page_no"] for call in chunk_repository.get_project_chunks.await_args_list],
            [1, 2],
        )
        self.controller.ensure_vector_index.assert_awaited_once_with(
            project=project,
            collection_name="staging-test",
        )
        self.controller.publish_staging_collection.assert_awaited_once_with(
            staging_collection="staging-test",
            project=project,
        )
        self.vector_db_client.delete_collection.assert_not_awaited()

    async def test_failed_project_index_cleans_up_staging_collection(self):
        from src.enums import ResponseSignal

        project = SimpleNamespace(id=9, project_id="project-1")
        project_repository = SimpleNamespace(
            get_project_or_create=AsyncMock(return_value=project)
        )
        chunk_repository = SimpleNamespace(
            get_project_chunks=AsyncMock(
                return_value=[SimpleNamespace(chunk_id=1)]
            )
        )
        self.controller.index_into_vector_db = AsyncMock(return_value=False)
        self.controller.create_staging_collection_name = lambda: "staging-test"
        self.vector_db_client.delete_collection = AsyncMock()

        result = await self.controller.index_project_chunks(
            project_id="project-1",
            project_repository=project_repository,
            chunk_repository=chunk_repository,
            do_reset=True,
        )

        self.assertEqual(result.signal, ResponseSignal.INSERT_INTO_VECTORDB_ERROR)
        self.assertEqual(result.inserted_items_count, 0)
        self.vector_db_client.delete_collection.assert_awaited_once_with(
            collection_name="staging-test"
        )


if __name__ == "__main__":
    unittest.main()
