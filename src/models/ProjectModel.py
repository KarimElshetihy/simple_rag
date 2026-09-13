from .db_schemes import Project
from .BaseDataModel import BaseDataModel
from ..enums.Database_Enums import DatabaseEnum


class ProjectModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)

        self.collection = self.db_client[DatabaseEnum.COLLECTION_PROJECT_NAME.value]

    async def init_collection(self):
        db_collections = await self.db_client.list_collection_names()
        if DatabaseEnum.COLLECTION_PROJECT_NAME.value not in db_collections:
            await self.db_client.create_collection(DatabaseEnum.COLLECTION_PROJECT_NAME.value)
            for index in Project.get_index():
                await self.collection.create_index(
                    index["key"], 
                    unique=index["unique"], 
                    name=index["name"]
                )
    
    async def create_project(self, project: Project):
        result = await self.collection.insert_one(project.model_dump())
        project.id = result.inserted_id

        return project

    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client=db_client)
        await instance.init_collection()
        return instance


    async def get_project_or_create(self, project_id: str):
        record = await self.collection.find_one({"project_id": project_id})

        if record is None:
            project = Project(project_id=project_id)
            project = await self.create_project(project=project)

            return project

        return Project(**record)

    async def get_all_projects(self, page: int = 1, page_size: int = 20):
        # Count total number of documents
        total_documents = await self.collection.count_documents({})

        # Calculate total number of pages
        total_pages = total_documents // page_size
        if total_documents % page_size > 0:
            total_pages += 1

        cursor = self.collection.find().skip((page - 1) * page_size).limit(page_size)

        projects = []
        async for document in cursor:
            projects.append(Project(**document))

        return projects, total_pages
