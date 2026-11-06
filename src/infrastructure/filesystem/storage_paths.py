from pathlib import Path

from src.helpers.config import get_settings


class StoragePaths:
    def __init__(self, data_dir: str | Path | None = None):
        configured_data_dir = (
            Path(data_dir).expanduser()
            if data_dir is not None
            else Path(get_settings().DATA_DIR).expanduser()
        )
        repository_root = Path(__file__).resolve().parents[3]
        self.data_dir = (
            configured_data_dir
            if configured_data_dir.is_absolute()
            else repository_root / configured_data_dir
        ).resolve()
        self.uploads_dir = self.data_dir / "uploaded_files"
        self.vector_db_dir = self.data_dir / "vector_db"

    def get_project_path(self, project_id: str) -> str:
        project_path = self.uploads_dir / project_id
        project_path.mkdir(parents=True, exist_ok=True)
        return str(project_path)

    def get_vector_db_path(self, db_name: str) -> str:
        vector_db_path = self.vector_db_dir / db_name
        vector_db_path.mkdir(parents=True, exist_ok=True)
        return str(vector_db_path)
