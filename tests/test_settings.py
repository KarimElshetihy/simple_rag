import unittest

from pydantic import ValidationError

from src.helpers.config import Settings


class SettingsTests(unittest.TestCase):
    def test_example_environment_file_parses_with_typed_settings(self):
        settings = Settings(_env_file="src/.env.example")

        self.assertEqual(settings.GENERATION_BACKEND, "OPENAI")
        self.assertEqual(settings.EMBEDDING_BACKEND, "OPENAI")
        self.assertEqual(settings.VECTOR_DB_BACKEND, "PGVECTOR")
        self.assertEqual(settings.FILE_SUPPORTED_TYPES, ["text/plain", "application/pdf"])
        self.assertEqual(settings.PGVECTOR_INDEX_TYPE, "hnsw")
        self.assertEqual(settings.OCR_LANGUAGES, "eng+ara")
        self.assertEqual(
            settings.TESSERACT_CMD,
            "C:/Program Files/Tesseract-OCR/tesseract.exe",
        )
        self.assertEqual(
            settings.TESSDATA_DIR,
            "C:/Program Files/Tesseract-OCR/tessdata",
        )

    def test_unknown_provider_is_rejected(self):
        with self.assertRaises(ValidationError):
            Settings(
                _env_file=None,
                APP_NAME="test",
                APP_VERSION="1",
                FILE_SUPPORTED_TYPES=["text/plain"],
                FILE_MAX_SIZE=10,
                FILE_DEFAULT_CHUNK_SIZE=1024,
                GENERATION_BACKEND="unsupported",
                EMBEDDING_BACKEND="OPENAI",
            )

    def test_retired_dotenv_keys_are_ignored(self):
        settings = Settings(
            _env_file=None,
            APP_NAME="test",
            APP_VERSION="1",
            FILE_SUPPORTED_TYPES=["text/plain"],
            FILE_MAX_SIZE=10,
            FILE_DEFAULT_CHUNK_SIZE=1024,
            GENERATION_BACKEND="OPENAI",
            EMBEDDING_BACKEND="OPENAI",
            POSTGRES_HOST="localhost",
            VECTOR_DB_BACKEND_LITERAL=["QDRANT", "PGVECTOR"],
        )

        self.assertEqual(settings.GENERATION_BACKEND, "OPENAI")
        self.assertFalse(hasattr(settings, "POSTGRES_HOST"))
        self.assertFalse(hasattr(settings, "VECTOR_DB_BACKEND_LITERAL"))


if __name__ == "__main__":
    unittest.main()
