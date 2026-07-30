from fastapi import FastAPI, APIRouter, Depends
from ..helpers.config import Settings, get_settings
import os

base_router = APIRouter(
    prefix="/api/v1",
    tags=["base"],
)

@base_router.get("/")
async def root(app_settings: Settings = Depends(get_settings)):

    app_settings = get_settings()
    app_name = app_settings.APP_NAME
    app_version = app_settings.APP_VERSION
    
    return {
        "message": f"Welcome to {app_name} API v{app_version}!"
    }