import unittest

from src.helpers.timing import log_async_duration, log_duration


class TimingTests(unittest.IsolatedAsyncioTestCase):
    async def test_sync_duration_logs_success(self):
        with self.assertLogs("uvicorn.error", level="INFO") as captured_logs:
            with log_duration("test.sync", project_id="project-1"):
                pass

        self.assertIn("operation=test.sync status=completed", captured_logs.output[0])
        self.assertIn("project_id=project-1", captured_logs.output[0])
        self.assertIn("duration_seconds=", captured_logs.output[0])

    async def test_sync_duration_logs_and_reraises_errors(self):
        with self.assertLogs("uvicorn.error", level="ERROR") as captured_logs:
            with self.assertRaisesRegex(ValueError, "test failure"):
                with log_duration("test.sync"):
                    raise ValueError("test failure")

        self.assertIn("status=error", captured_logs.output[0])
        self.assertIn("error_type=ValueError", captured_logs.output[0])
        self.assertNotIn("test failure", captured_logs.output[0])

    async def test_async_duration_logs_success(self):
        with self.assertLogs("uvicorn.error", level="INFO") as captured_logs:
            async with log_async_duration("test.async", items=3):
                pass

        self.assertIn("operation=test.async status=completed", captured_logs.output[0])
        self.assertIn("items=3", captured_logs.output[0])
        self.assertIn("duration_seconds=", captured_logs.output[0])

    async def test_async_duration_logs_and_reraises_errors(self):
        with self.assertLogs("uvicorn.error", level="ERROR") as captured_logs:
            with self.assertRaisesRegex(ValueError, "test failure"):
                async with log_async_duration("test.async"):
                    raise ValueError("test failure")

        self.assertIn("status=error", captured_logs.output[0])
        self.assertIn("error_type=ValueError", captured_logs.output[0])
        self.assertNotIn("test failure", captured_logs.output[0])


if __name__ == "__main__":
    unittest.main()
