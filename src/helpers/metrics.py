import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, Counter, Histogram
from prometheus_client import generate_latest


ASGIMessage = dict[str, Any]
ASGIReceive = Callable[[], Awaitable[ASGIMessage]]
ASGISend = Callable[[ASGIMessage], Awaitable[None]]
ASGIApp = Callable[[dict[str, Any], ASGIReceive, ASGISend], Awaitable[None]]


class PrometheusMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        request_count: Counter,
        request_latency: Histogram,
    ):
        self.app = app
        self.request_count = request_count
        self.request_latency = request_latency

    async def __call__(
        self, scope: dict[str, Any], receive: ASGIReceive, send: ASGISend
    ) -> None:
        if scope["type"] != "http" or scope.get("path") == "/metrics":
            await self.app(scope, receive, send)
            return

        started_at = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_status(message: ASGIMessage) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        except Exception:
            if not response_started:
                status_code = 500
            raise
        finally:
            route = scope.get("route")
            endpoint = getattr(route, "path", "unmatched")
            labels = {
                "method": scope["method"],
                "endpoint": endpoint,
            }
            self.request_latency.labels(**labels).observe(
                time.perf_counter() - started_at
            )
            self.request_count.labels(
                **labels,
                status=str(status_code),
            ).inc()


def setup_metrics(app: FastAPI) -> CollectorRegistry:
    registry = CollectorRegistry()
    request_count = Counter(
        "http_requests_total",
        "Total HTTP requests",
        ("method", "endpoint", "status"),
        registry=registry,
    )
    request_latency = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency in seconds",
        ("method", "endpoint"),
        registry=registry,
    )

    app.add_middleware(
        PrometheusMiddleware,
        request_count=request_count,
        request_latency=request_latency,
    )

    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint() -> Response:
        return Response(
            content=generate_latest(registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    return registry
