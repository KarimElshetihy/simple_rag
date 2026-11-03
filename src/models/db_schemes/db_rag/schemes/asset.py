from .db_rag_base import DB_BASE
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship


class Asset(DB_BASE):
    __tablename__ = "assets"

    asset_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    asset_project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        nullable=False,
        index=True,
    )
    asset_name = Column(String, nullable=False)
    asset_type = Column(String, nullable=False)
    asset_size = Column(Integer, nullable=False)
    asset_path = Column(String, nullable=False)
    asset_config = Column(JSONB, nullable=True)
    asset_original_name = Column(String, nullable=False)
    asset_upload_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    project = relationship("Project", back_populates="assets")
    chunks = relationship("AssetChunk", back_populates="asset")