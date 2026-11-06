from pydantic import BaseModel


class RetrievedDocument(BaseModel):
    text: str
    score: float
    chunk_id: int | None = None
