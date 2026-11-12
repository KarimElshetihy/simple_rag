from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums.job_status import JobStatus
from src.models.db_schemes.db_rag.schemes.processing_job import ProcessingJob


class ProcessingJobRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        job_id: str,
        project_id: str,
        file_id: str | None,
    ) -> ProcessingJob:
        job = ProcessingJob(
            job_id=job_id,
            project_id=project_id,
            file_id=file_id,
            status=JobStatus.QUEUED.value,
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def get_by_id(self, job_id: str) -> ProcessingJob | None:
        result = await self.session.execute(
            select(ProcessingJob).where(ProcessingJob.job_id == job_id)
        )
        return result.scalar_one_or_none()

    async def mark_running(self, job_id: str) -> None:
        await self._update(
            job_id,
            status=JobStatus.RUNNING.value,
            started_at=func.coalesce(ProcessingJob.started_at, func.now()),
            updated_at=func.now(),
        )

    async def mark_succeeded(
        self,
        job_id: str,
        result: dict[str, int | str],
    ) -> None:
        await self._update(
            job_id,
            status=JobStatus.SUCCEEDED.value,
            result=result,
            error_message=None,
            completed_at=func.now(),
            updated_at=func.now(),
        )

    async def mark_failed(
        self,
        job_id: str,
        error_message: str,
        *,
        only_if_queued: bool = False,
    ) -> bool:
        conditions = [ProcessingJob.job_id == job_id]
        if only_if_queued:
            conditions.append(ProcessingJob.status == JobStatus.QUEUED.value)
        result = await self.session.execute(
            update(ProcessingJob)
            .where(*conditions)
            .values(
                status=JobStatus.FAILED.value,
                error_message=error_message,
                completed_at=func.now(),
                updated_at=func.now(),
            )
        )
        return result.rowcount == 1

    async def _update(self, job_id: str, **values: object) -> None:
        result = await self.session.execute(
            update(ProcessingJob)
            .where(ProcessingJob.job_id == job_id)
            .values(**values)
        )
        if result.rowcount != 1:
            raise LookupError(f"Processing job {job_id} does not exist.")
