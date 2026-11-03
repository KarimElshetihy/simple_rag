from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .db_schemes.db_rag.schemes.project import Project


class ProjectModel:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_project_or_create(self, project_id: str):
        result = await self.session.execute(
            select(Project).where(Project.project_id == project_id)
        )
        project = result.scalar_one_or_none()

        if project is None:
            project = Project(project_id=project_id)
            self.session.add(project)
            await self.session.flush()

        return project

    async def get_all_projects(self, page: int = 1, page_size: int = 20):
        total_documents = await self.session.scalar(
            select(func.count()).select_from(Project)
        )
        total_pages = (total_documents + page_size - 1) // page_size
        result = await self.session.execute(
            select(Project)
            .order_by(Project.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        projects = list(result.scalars().all())

        return projects, total_pages
