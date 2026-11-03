from .db_rag_base import DB_BASE
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from datetime import datetime

class Project(DB_BASE):
    __tablename__ = "projects"

    project_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    assets = relationship("Asset", back_populates="project")