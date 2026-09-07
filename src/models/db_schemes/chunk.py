from pydantic import BaseModel, Field, field_validator
from typing import Optional
from bson.objectid import ObjectId


class Chunk(BaseModel):
    _id: Optional[ObjectId]
    chunk_id: str = Field(min_length=1)
    chunk_project_id: ObjectId
    chunk_text: str = Field(min_length=1)
    chunk_metadata: dict
    chunk_order: int = Field(gt=0)

    @field_validator("chunk_id")
    def validate(cls, value):
        if not value.isalnun():
            raise ValueError("chunk_id must be alphanumeric")
        return value

    class Config:
        arbitrary_types_allowed = True
