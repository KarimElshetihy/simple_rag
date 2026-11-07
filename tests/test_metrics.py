import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.helpers.metrics import setup_metrics


class MetricsTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        self.registry = setup_metrics(app)

        @app.get("/projects/{project_id}")
        def get_project(project_id: str):
            return {"project_id": project_id}

        @app.get("/raises")
        def raises():
            raise RuntimeError("request failed")

        self.client = TestClient(app, raise_server_exceptions=False)

    def test_records_requests_using_route_templates(self):
        first = self.client.get("/projects/project-one")
        second = self.client.get("/projects/project-two")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        metrics = self.client.get("/metrics").text

        self.assertIn(
            'http_requests_total{endpoint="/projects/{project_id}",method="GET",status="200"} 2.0',
            metrics,
        )
        self.assertNotIn("project-one", metrics)
        self.assertNotIn("project-two", metrics)

    def test_records_server_errors(self):
        response = self.client.get("/raises")

        self.assertEqual(response.status_code, 500)
        metrics = self.client.get("/metrics").text
        self.assertIn(
            'http_requests_total{endpoint="/raises",method="GET",status="500"} 1.0',
            metrics,
        )

    def test_metrics_scrapes_are_not_counted(self):
        self.client.get("/projects/project-one")
        before = self.registry.get_sample_value(
            "http_requests_total",
            {"endpoint": "/projects/{project_id}", "method": "GET", "status": "200"},
        )

        self.client.get("/metrics")

        after = self.registry.get_sample_value(
            "http_requests_total",
            {"endpoint": "/projects/{project_id}", "method": "GET", "status": "200"},
        )
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
