import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from src.routes.health import health_router


class FakeConnection:
    def __init__(self, error: Exception | None = None):
        self.error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        return False

    async def execute(self, statement):
        if self.error is not None:
            raise self.error
        return None


class FakeEngine:
    def __init__(self, connection: FakeConnection):
        self.connection = connection

    def connect(self):
        return self.connection


class HealthTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(health_router)
        self.app = app
        self.client = TestClient(app, raise_server_exceptions=False)

    def test_health_returns_ok_when_database_query_succeeds(self):
        self.app.state.db_engine = FakeEngine(FakeConnection())

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_returns_service_unavailable_when_database_is_not_initialized(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"detail": "Database is not initialized."},
        )

    def test_health_returns_service_unavailable_when_database_query_fails(self):
        error = OperationalError("SELECT 1", {}, OSError("connection refused"))
        self.app.state.db_engine = FakeEngine(FakeConnection(error))

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"detail": "Database unavailable."})


if __name__ == "__main__":
    unittest.main()
