"""T5.2 — FastAPI application entrypoint.

Creates the ASGI app, wires dependencies, registers the API router.
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.db import init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="MBclaw", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health():
    """Liveness check: DB and basic config are reachable."""
    db_ok = os.path.exists(os.getenv("MBCLAW_DB_PATH", "data/mbclaw.db"))
    return {"db_ok": db_ok, "version": "0.1.0"}
