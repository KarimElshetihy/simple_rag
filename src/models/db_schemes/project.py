from pydantic import BaseModel, Field, field_validator
from typing import Optional
from bson.objectid import ObjectId


class Project(BaseModel):
    id: Optional[ObjectId] = Field(None, alias="_id")
    project_id: str = Field(min_length=1)

    @field_validator("project_id")
    def validate(cls, value):
        if not value.isalnum():
            raise ValueError("project_id must be alphanumeric")
        return value

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def get_index(cls):
        return [{"key": [("project_id", 1)], "unique": True, "name": "project_index"}]

