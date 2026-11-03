from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db_schemes.db_rag.schemes.asset import Asset


class AssetModel:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_asset(self, asset: Asset):
        self.session.add(asset)
        await self.session.flush()
        return asset

    async def get_all_project_assets(self, asset_project_id: int, asset_type: str):
        result = await self.session.execute(
            select(Asset)
            .where(
                Asset.asset_project_id == asset_project_id,
                Asset.asset_type == asset_type,
            )
            .order_by(Asset.asset_id)
        )
        return list(result.scalars().all())

    async def get_asset_record(self, asset_project_id: int, asset_name: str):
        result = await self.session.execute(
            select(Asset).where(
                Asset.asset_project_id == asset_project_id,
                Asset.asset_name == asset_name,
            )
        )
        return result.scalar_one_or_none()