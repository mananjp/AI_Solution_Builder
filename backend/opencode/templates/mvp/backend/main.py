import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("uvicorn.error")

# Hybrid imports: supports both top-level uvicorn execution and package imports
try:
    from . import db  # noqa: E402
    from .core.config import settings
    from .routers import router
    try:
        from .models import Base
    except (ImportError, ValueError):
        Base = None
except (ImportError, ValueError):
    import db  # noqa: E402
    from core.config import settings
    from routers import router
    try:
        from models import Base
    except (ImportError, ValueError):
        Base = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-create database tables on startup so initial queries succeed
    if Base is not None:
        try:
            async with db.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables verified/created successfully.")
        except Exception as exc:
            logger.warning("Database table creation skipped on startup: %s", exc)
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
    allow_origins=settings.CORS_ORIGINS if settings.CORS_ORIGINS else ["*"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|.*\.onrender\.com|.*\.vercel\.app)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix=settings.API_PREFIX)
