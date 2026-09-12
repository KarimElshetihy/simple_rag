from pydantic import BaseModel, Field, field_validator
from typing import Optional
from bson.objectid import ObjectId


class Chunk(BaseModel):
    id: Optional[ObjectId] = Field(None, alias="_id")
    chunk_project_id: ObjectId
    chunk_text: str = Field(min_length=1)
    chunk_metadata: dict
    chunk_order: int = Field(gt=0)

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def get_index(cls):
        return [{"key": [("chunk_project_id", 1)], "unique": False, "name": "chunk_project_index"}]

