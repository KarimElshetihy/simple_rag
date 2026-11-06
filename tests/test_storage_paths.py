import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.infrastructure.filesystem import StoragePaths


class StoragePathTests(unittest.TestCase):
    def test_runtime_paths_use_configured_data_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_directory = Path(temporary_directory) / "runtime-data"
            paths = StoragePaths(data_dir=data_directory)
            project_path = paths.get_project_path("project-1")
            vector_path = paths.get_vector_db_path("qdrant")

            self.assertEqual(project_path, str(data_directory / "uploaded_files" / "project-1"))
            self.assertEqual(vector_path, str(data_directory / "vector_db" / "qdrant"))
            self.assertTrue(Path(project_path).is_dir())
            self.assertTrue(Path(vector_path).is_dir())

    def test_relative_data_directory_is_resolved_from_repository_root(self):
        repository_root = Path(__file__).resolve().parents[1]
        with patch(
            "src.infrastructure.filesystem.storage_paths.get_settings",
            return_value=SimpleNamespace(DATA_DIR="test-runtime-data"),
        ):
            paths = StoragePaths()

        self.assertEqual(
            paths.data_dir,
            repository_root / "test-runtime-data",
        )


if __name__ == "__main__":
    unittest.main()
