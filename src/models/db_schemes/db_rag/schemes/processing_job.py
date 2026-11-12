from sqlalchemy import Column, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from .db_rag_base import DB_BASE


class ProcessingJob(DB_BASE):
    __tablename__ = "processing_jobs"

    job_id = Column(String(36), primary_key=True)
    project_id = Column(String, nullable=False, index=True)
    file_id = Column(String, nullable=True)
    status = Column(String(16), nullable=False, index=True)
    result = Column(JSONB, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
