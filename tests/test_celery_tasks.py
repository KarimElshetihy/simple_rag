import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from src.enums.database_enums import BackendDBEnum
from src.enums.response_enums import ResponseSignal
from src.infrastructure.celery.app import celery_app
from src.infrastructure.celery.tasks import process_project_files


class CeleryDocumentTaskTests(unittest.TestCase):
    def setUp(self):
        self.settings = SimpleNamespace(
            DATABASE_BACKEND=BackendDBEnum.POSTGRES,
            POSTGRES_URI="postgresql+asyncpg://localhost/test",
        )
        self.engine = MagicMock()
        self.engine.dispose = AsyncMock()
        self.session = MagicMock()
        self.session_context = MagicMock()
        self.session_context.__aenter__ = AsyncMock(return_value=self.session)
        self.session_context.__aexit__ = AsyncMock(return_value=False)
        self.transaction_context = MagicMock()
        self.transaction_context.__aenter__ = AsyncMock()
        self.transaction_context.__aexit__ = AsyncMock(return_value=False)
        self.session.begin.return_value = self.transaction_context

        self.service = MagicMock()
        self.service.process_project_files = AsyncMock(
            return_value=SimpleNamespace(
                signal=ResponseSignal.PROCESSING_SUCCESS,
                inserted_chunks=8,
                processed_files=1,
            )
        )

        patches = (
            patch(
                "src.infrastructure.celery.tasks.get_settings",
                return_value=self.settings,
            ),
            patch(
                "src.infrastructure.celery.tasks.create_async_engine",
                return_value=self.engine,
            ),
            patch(
                "src.infrastructure.celery.tasks.async_sessionmaker",
                return_value=lambda: self.session_context,
            ),
            patch(
                "src.infrastructure.celery.tasks.DocumentProcessingService",
                return_value=self.service,
            ),
            patch("src.infrastructure.celery.tasks.ProjectRepository"),
            patch("src.infrastructure.celery.tasks.AssetRepository"),
            patch("src.infrastructure.celery.tasks.ChunkRepository"),
        )
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_task_runs_async_service_and_disposes_worker_engine(self):
        result = process_project_files.run(
            project_id="project-1",
            file_id="document.txt",
            chunk_size=500,
            overlap_size=50,
            do_reset=True,
        )

        self.assertEqual(
            result,
            {
                "signal": ResponseSignal.PROCESSING_SUCCESS.value,
                "inserted_chunks": 8,
                "processed_files": 1,
            },
        )
        self.service.process_project_files.assert_awaited_once()
        self.engine.dispose.assert_awaited_once()
        self.transaction_context.__aexit__.assert_awaited_once_with(
            None, None, None
        )

    def test_processing_signal_failure_fails_task_and_disposes_engine(self):
        self.service.process_project_files.return_value = SimpleNamespace(
            signal=ResponseSignal.FILE_ERROR,
            inserted_chunks=0,
            processed_files=0,
        )

        with self.assertRaisesRegex(RuntimeError, "No file found"):
            process_project_files.run(project_id="project-1", file_id="missing.txt")

        self.engine.dispose.assert_awaited_once()
        exception_type = self.transaction_context.__aexit__.await_args.args[0]
        self.assertIs(exception_type, RuntimeError)

    def test_celery_app_registers_worker_task_module(self):
        self.assertIn(
            "src.infrastructure.celery.tasks",
            celery_app.conf.include,
        )


if __name__ == "__main__":
    unittest.main()
