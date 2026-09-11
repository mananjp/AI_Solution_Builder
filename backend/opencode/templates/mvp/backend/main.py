from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import database engine so lifespan can reach the pool.
from . import db  # noqa: E402
from .core.config import settings
from .routers import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await db.engine.dispose()


app = FastAPI(
    title=settings.APP_TITLE,
    version="0.1.0",
    docs_url="/docs",
    openapi_url=f"{settings.API_PREFIX}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.API_PREFIX)
