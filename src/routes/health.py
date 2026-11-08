import logging

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


logger = logging.getLogger(__name__)
health_router = APIRouter()


@health_router.get("/health", include_in_schema=False)
async def health(request: Request) -> dict[str, str]:
    db_engine = getattr(request.app.state, "db_engine", None)
    if db_engine is None:
        raise HTTPException(status_code=503, detail="Database is not initialized.")

    try:
        async with db_engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.exception("Readiness check failed: PostgreSQL is unavailable.")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable.",
        ) from exc

    return {"status": "ok"}
