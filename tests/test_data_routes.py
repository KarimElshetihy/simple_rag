import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from kombu.exceptions import OperationalError

from src.infrastructure.celery.tasks import process_project_files
from src.routes.data import data_router


class ProcessFileRouteTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(data_router)
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_process_file_enqueues_task_and_returns_accepted(self):
        with patch(
            "src.routes.data.run_in_threadpool",
            new=AsyncMock(return_value=SimpleNamespace(id="task-123")),
        ) as enqueue:
            response = self.client.post(
                "/api/v1/data/process_file/project-1",
                json={
                    "file_id": "document.pdf",
                    "chunk_size": 500,
                    "overlap_size": 50,
                    "do_reset": True,
                },
            )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(
            response.json(),
            {"message": "processing_queued", "task_id": "task-123"},
        )
        enqueue.assert_awaited_once_with(
            process_project_files.delay,
            project_id="project-1",
            file_id="document.pdf",
            chunk_size=500,
            overlap_size=50,
            do_reset=True,
        )

    def test_process_file_returns_service_unavailable_if_broker_is_down(self):
        with patch(
            "src.routes.data.run_in_threadpool",
            new=AsyncMock(side_effect=OperationalError("broker unavailable")),
        ):
            with self.assertLogs("uvicorn.error", level="ERROR"):
                response = self.client.post(
                    "/api/v1/data/process_file/project-1",
                    json={"file_id": "document.pdf"},
                )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"message": "processing_queue_unavailable"},
        )

    def test_process_file_rejects_invalid_chunk_overlap(self):
        with patch("src.routes.data.run_in_threadpool") as enqueue:
            response = self.client.post(
                "/api/v1/data/process_file/project-1",
                json={"chunk_size": 100, "overlap_size": 100},
            )

        self.assertEqual(response.status_code, 422)
        enqueue.assert_not_called()


if __name__ == "__main__":
    unittest.main()
