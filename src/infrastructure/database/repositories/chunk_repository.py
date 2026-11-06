from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db_schemes.db_rag.schemes.chunk import AssetChunk


class ChunkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_chunk(self, chunk: AssetChunk):
        self.session.add(chunk)
        await self.session.flush()
        return chunk

    async def get_chunk(self, chunk_id: int):
        return await self.session.get(AssetChunk, chunk_id)

    async def insert_many_chunks(self, chunks: list, batch_size: int = 100):
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            self.session.add_all(batch)
            await self.session.flush()

        return len(chunks)

    async def delete_chunks_by_project_id(self, project_id: int):
        result = await self.session.execute(
            delete(AssetChunk).where(AssetChunk.chunk_project_id == project_id)
        )
        return result.rowcount

    async def get_all_chunks(self, page: int = 1, page_size: int = 20):
        total_documents = await self.session.scalar(
            select(func.count()).select_from(AssetChunk)
        )
        total_pages = (total_documents + page_size - 1) // page_size
        result = await self.session.execute(
            select(AssetChunk)
            .order_by(AssetChunk.chunk_id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        chunks = list(result.scalars().all())

        return chunks, total_pages

    async def get_project_chunks(
        self, project_id: int, page_no: int = 1, page_size: int = 50
    ):
        result = await self.session.execute(
            select(AssetChunk)
            .where(AssetChunk.chunk_project_id == project_id)
            .order_by(AssetChunk.chunk_id)
            .offset((page_no - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all())
