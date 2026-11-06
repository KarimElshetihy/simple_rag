from pydantic import BaseModel, Field, field_validator


class PushRequest(BaseModel):
    do_reset: bool = False


class SearchRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=5, ge=1, le=20)

    @field_validator("text")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must contain non-whitespace characters")
        return value