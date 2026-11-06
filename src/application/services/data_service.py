from src.enums import ResponseSignal
from src.helpers.config import get_settings
from src.infrastructure.filesystem import StoragePaths
from fastapi import UploadFile
import logging
import re
import os
import aiofiles
from dataclasses import dataclass

from src.enums.asset_enums import AssetTypeEnum
from src.infrastructure.database.repositories import (
    AssetRepository,
    ProjectRepository,
)
from src.models.db_schemes.db_rag.schemes.asset import Asset
from src.models.db_schemes.db_rag.schemes.project import Project

logger = logging.getLogger("uvicorn.error")


class FileUploadError(Exception):
    pass


@dataclass
class UploadedAssetResult:
    upload_message: str
    project: Project
    asset: Asset


class DataService:
    def __init__(self):
        self.app_settings = get_settings()
        self.storage_paths = StoragePaths()
        self.size_scale = 1048576  # convert MB to bytes

    def validate_uploaded_file(self, file: UploadFile):

        if file.content_type not in self.app_settings.FILE_SUPPORTED_TYPES:
            return False, ResponseSignal.FILE_TYPE_NOT_SUPPORTED.value

        if file.size > self.app_settings.FILE_MAX_SIZE * self.size_scale:
            return False, ResponseSignal.FILE_SIZE_EXCEEDED.value

        return True, ResponseSignal.FILE_VALIDATED_SUCCESS.value

    def get_clean_file_name(self, orig_file_name: str):

        # remove any special characters, except underscore and .
        cleaned_file_name = re.sub(r"[^\w.]", "", orig_file_name.strip())

        # replace spaces with underscore
        cleaned_file_name = cleaned_file_name.replace(" ", "_")

        return cleaned_file_name

    def generate_unique_file_path(self, orig_file_name: str, project_id: str):

        random_key = self.generate_key()
        project_path = self.storage_paths.get_project_path(project_id=project_id)

        cleaned_file_name = self.get_clean_file_name(orig_file_name=orig_file_name)

        new_file_path = os.path.join(project_path, random_key + "_" + cleaned_file_name)

        while os.path.exists(new_file_path):
            random_key = self.generate_key()
            new_file_path = os.path.join(
                project_path, random_key + "_" + cleaned_file_name
            )

        return new_file_path, random_key + "_" + cleaned_file_name

    async def upload_file_to_path(self, file: UploadFile, file_path: str):

        try:
            async with aiofiles.open(file_path, "wb") as f:
                while chunk := await file.read(
                    self.app_settings.FILE_DEFAULT_CHUNK_SIZE
                ):
                    await f.write(chunk)

            return ResponseSignal.FILE_UPLOAD_SUCCESS.value
        except Exception:
            try:
                os.remove(file_path)
            except FileNotFoundError:
                pass
            except OSError:
                logger.exception("Failed to remove incomplete upload %s", file_path)
            raise

    async def upload_and_register_file(
        self,
        file: UploadFile,
        project_id: str,
        project_repository: ProjectRepository,
        asset_repository: AssetRepository,
    ) -> UploadedAssetResult:
        new_file_path, unique_file_name = self.generate_unique_file_path(
            orig_file_name=file.filename,
            project_id=project_id,
        )
        try:
            upload_message = await self.upload_file_to_path(
                file=file,
                file_path=new_file_path,
            )
        except Exception as error:
            raise FileUploadError from error

        try:
            project = await project_repository.get_project_or_create(
                project_id=project_id
            )
            asset = Asset(
                asset_project_id=project.id,
                asset_type=AssetTypeEnum.FILE.value,
                asset_name=unique_file_name,
                asset_size=file.size,
                asset_path=new_file_path,
                asset_original_name=file.filename,
            )
            asset_record = await asset_repository.create_asset(asset=asset)
        except Exception:
            try:
                os.remove(new_file_path)
            except FileNotFoundError:
                pass
            except OSError:
                logger.exception("Failed to remove uploaded file %s", new_file_path)
            raise

        return UploadedAssetResult(
            upload_message=upload_message,
            project=project,
            asset=asset_record,
        )
