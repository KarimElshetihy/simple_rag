from .db_rag_base import DB_BASE
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship


class Project(DB_BASE):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, unique=True, nullable=True, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    assets = relationship("Asset", back_populates="project")
    chunks = relationship("AssetChunk", back_populates="project")