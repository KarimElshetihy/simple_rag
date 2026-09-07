from fastapi import FastAPI
from src.routes import base, data
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
from src.helpers.config import get_settings


# ------------ LIFESPAN EVENT HANDLER ------------ #
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. On Startup: Initialize the Motor client
    setting = get_settings()
    app.state.mongo_client = AsyncIOMotorClient(setting.MONGODB_URI)
    app.state.db = app.state.mongo_client[setting.MONGODB_DB_NAME]
    

    # Optional: Analogous to "create_all", you can build indexes here on startup
    # await app.state.db["users"].create_index([("email", 1)], unique=True)

    yield

    # 2. On Shutdown: Close the Motor client connection cleanly
    app.state.mongo_client.close()


app = FastAPI(lifespan=lifespan)
app.include_router(base.base_router)
app.include_router(data.data_router)
