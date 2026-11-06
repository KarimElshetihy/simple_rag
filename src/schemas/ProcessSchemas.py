from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ProcessRequest(BaseModel):
    file_id: Optional[str] = None
    chunk_size: int = Field(default=1000, ge=1, le=8192)
    overlap_size: int = Field(default=150, ge=0, le=8191)
    do_reset: int = 0

    @model_validator(mode="after")
    def validate_chunk_overlap(self):
        if self.overlap_size >= self.chunk_size:
            raise ValueError("overlap_size must be smaller than chunk_size")
        return self
