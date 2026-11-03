from .db_rag_base import DB_BASE
from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from pydantic import BaseModel

class AssetChunk(DB_BASE):
    __tablename__ = "asset_chunks"

    chunk_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    text = Column(String, unique=True, index=True)
    chunk_metadata = Column(JSONB, nullable=False)
    order = Column(String, nullable=False)
    text_size = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False) # Foreign key to Project (not enforced here)
    asset_id = Column(Integer, ForeignKey("assets.asset_id"), nullable=False) # Foreign key to Asset (not enforced here)
    asset = relationship("Asset", back_populates="chunks")  # Relationship to Asset
    __table_args__ = (
        Index('ix_asset_chunks_asset_id', 'asset_id'),
        Index('ix_asset_chunks_project_id', 'project_id'),  # Index on project_id for faster lookups
        Index('ix_asset_chunks_order', 'order'),  # Index on order for faster look
    )

class RetrievedDocument(BaseModel):
    text: str
    score: float