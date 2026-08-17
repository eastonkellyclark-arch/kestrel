"""Standalone entrypoint: python -m backend.run or python backend/run.py"""

import uvicorn

from app.settings import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=True)
