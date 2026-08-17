"""Kestrel API — FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import init_db
from .settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Kestrel", lifespan=lifespan)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "database": str(settings.database_path),
    }
