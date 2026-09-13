from .db_schemes import Asset
from .BaseDataModel import BaseDataModel
from ..enums.Database_Enums import DatabaseEnum
from bson import ObjectId


class AssetModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.collection = self.db_client[DatabaseEnum.COLLECTION_ASSET_NAME.value]

    async def init_collection(self):
        db_collections = await self.db_client.list_collection_names()
        if DatabaseEnum.COLLECTION_ASSET_NAME.value not in db_collections:
            await self.db_client.create_collection(DatabaseEnum.COLLECTION_ASSET_NAME.value)
            for index in Asset.get_index():
                await self.collection.create_index(
                    index["key"], 
                    unique=index["unique"], 
                    name=index["name"]
                )

    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client=db_client)
        await instance.init_collection()
        return instance

    async def create_asset(self, asset: Asset):
        result = await self.collection.insert_one(asset.model_dump(by_alias=True, exclude_unset=True))
        asset.id = result.inserted_id
        return asset

    async def get_all_project_assets(self, asset_project_id: str):
        return await self.collection.find({"asset_project_id": ObjectId(asset_project_id)}).to_list(length=None)