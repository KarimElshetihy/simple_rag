from .db_rag_base import DB_BASE
from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

class Asset(DB_BASE):
    __tablename__ = "assets"

    asset_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, unique=True, index=True)
    type = Column(String, nullable=False)
    size = Column(String, nullable=False)
    config = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    project_id = Column(Integer, ForeignKey("projects.project_id"), nullable=False) # Foreign key to Project (not enforced here)
    project = relationship("Project", back_populates="assets")  # Relationship to Project
    __table_args__ = (
        Index('ix_assets_project_id', 'project_id'),  # Index on project_id for faster lookups
        Index('ix_assets_type', 'type'),  # Index on type for faster lookups
    )

    chunks = relationship("AssetChunk", back_populates="asset")