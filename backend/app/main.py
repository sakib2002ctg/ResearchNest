from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.core.logging import logger
from app.database.database import engine
from app.exceptions.handlers import register_exception_handlers
from app.middleware.logging import LoggingMiddleware
from app.routers.auth import router as auth_router
from app.routers.papers import router as papers_router
from app.routers.research import router as research_router
from app.routers.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # Test database connection
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        logger.info("Connected to PostgreSQL successfully!")
        logger.info("ResearchNest application started.")

    except Exception:
        logger.exception("Database connection failed!")

    yield

    logger.info("ResearchNest application stopped.")


app = FastAPI(
    title="ResearchNest API",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(LoggingMiddleware)

# Register global exception handlers
register_exception_handlers(app)

# Versioned product API.
for router in (research_router, papers_router, users_router, auth_router):
    app.include_router(router, prefix="/api/v1")

# Temporary compatibility aliases use the same dependencies and authorization.
for router in (research_router, papers_router, auth_router):
    app.include_router(router, include_in_schema=False)


@app.get("/")
def home():
    return {"message": "Welcome to ResearchNest!"}


@app.get("/health")
def health():
    return {"status": "OK"}


@app.get("/about")
def about():
    return {"project": "ResearchNest", "version": "1.0"}
