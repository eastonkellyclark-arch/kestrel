"""Kestrel API — FastAPI application."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import router
from .database import init_db
from .settings import settings

logger = logging.getLogger("kestrel")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    logger.info("data_dir = %s", settings.data_dir)
    logger.info("database = %s", settings.database_path)
    init_db()
    yield


app = FastAPI(title="Kestrel", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database": str(settings.database_path),
    }
