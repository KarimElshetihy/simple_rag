import logging
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from time import perf_counter


logger = logging.getLogger("uvicorn.error")


def _format_context(context: dict[str, object]) -> str:
    return " ".join(f"{key}={value}" for key, value in context.items())


@contextmanager
def log_duration(operation: str, **context: object) -> Iterator[None]:
    started_at = perf_counter()
    try:
        yield
    except Exception as error:
        logger.error(
            "operation=%s status=error duration_seconds=%.3f error_type=%s %s",
            operation,
            perf_counter() - started_at,
            type(error).__name__,
            _format_context(context),
        )
        raise
    else:
        logger.info(
            "operation=%s status=completed duration_seconds=%.3f %s",
            operation,
            perf_counter() - started_at,
            _format_context(context),
        )


@asynccontextmanager
async def log_async_duration(operation: str, **context: object) -> AsyncIterator[None]:
    started_at = perf_counter()
    try:
        yield
    except Exception as error:
        logger.error(
            "operation=%s status=error duration_seconds=%.3f error_type=%s %s",
            operation,
            perf_counter() - started_at,
            type(error).__name__,
            _format_context(context),
        )
        raise
    else:
        logger.info(
            "operation=%s status=completed duration_seconds=%.3f %s",
            operation,
            perf_counter() - started_at,
            _format_context(context),
        )
