from pydantic import BaseModel, Field, field_validator
from typing import Optional
from bson.objectid import ObjectId
from datetime import datetime


class Asset(BaseModel):
    id: Optional[ObjectId] = Field(None, alias="_id")
    # asset_id: str = Field(min_length=1)
    asset_project_id: ObjectId
    asset_name: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    asset_size: int = Field(ge=0, default=None)
    asset_config: dict = Field(default=None)
    asset_upload_at: datetime = Field(default_factory=datetime.now)
    asset_original_name: str = Field(...,min_length=1)

    # @field_validator("asset_id")
    # def validate(cls, value):
    #     if not value.isalnum():
    #         raise ValueError("asset_id must be alphanumeric")
    #     return value

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def get_index(cls):
        return [
            {"key": [("asset_project_id", 1)], "unique": False, "name": "asset_project_index"},
            {"key": [("asset_project_id", 1),("asset_name",1)], "unique": True, "name": "asset_name_project_index"},
            ]