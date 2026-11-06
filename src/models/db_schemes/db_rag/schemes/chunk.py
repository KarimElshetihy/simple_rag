from .db_rag_base import DB_BASE
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship


class AssetChunk(DB_BASE):
    __tablename__ = "asset_chunks"

    chunk_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    chunk_project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )
    chunk_asset_id = Column(
        Integer,
        ForeignKey("assets.asset_id"),
        nullable=False,
        index=True,
    )
    chunk_text = Column(Text, nullable=False)
    chunk_metadata = Column("metadata", JSONB, nullable=False)
    chunk_order = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    project = relationship("Project", back_populates="chunks")
    asset = relationship("Asset", back_populates="chunks")