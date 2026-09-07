from .db_schemes import Chunk
from .BaseDataModel import BaseDataModel
from ..enums.Database_Enums import DatabaseEnum
from bson.objectid import ObjectId
from pymongo import InsertOne


class ChunkModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)

        self.collection = self.db_client[DatabaseEnum.COLLECTION_CHUNK_NAME.value]

    async def create_chunk(self, chunk: Chunk):
        result = await self.collection.insert_one(
            chunk.model_dump(by_alias=True, exclude_unset=True)
        )
        chunk._id = result.inserted_id

        return chunk

    async def get_chunk(self, chunk_id: str):
        record = await self.collection.find_one({"_id": ObjectId})

        if record is None:
            return None

        return Chunk(**record)

    async def insert_many_chunks(self, chunks: list, batch_size: int = 100):

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            operations = [
                InsertOne(chunk.model_dump(by_alias=True, exclude_unset=True))
                for chunk in batch
            ]

            await self.collection.bulk_write(operations)

        return len(chunks)

    async def delete_chunks_by_project_id(self, project_id: ObjectId):
        result = await self.collection.delete_many({"chunk_project_id": project_id})

        return result.deleted_count

    async def get_all_chunks(self, page: int = 1, page_size: int = 20):
        # Count total number of documents
        total_documents = await self.collection.count_documents({})

        # Calculate total number of pages
        total_pages = total_documents // page_size
        if total_documents % page_size > 0:
            total_pages += 1

        cursor = self.collection.find().skip((page - 1) * page_size).limit(page_size)

        chunks = []
        async for document in cursor:
            chunks.append(Chunk(**document))

        return chunks, total_pages
