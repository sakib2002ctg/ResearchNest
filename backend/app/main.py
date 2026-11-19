import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.core.logging import logger
from app.database.database import engine
from app.database.discovery_database import create_discovery_engine
from app.exceptions.handlers import register_exception_handlers
from app.middleware.logging import LoggingMiddleware
from app.modules.ai.gateway import AIProviderGateway
from app.modules.ai.router import router as conversations_router
from app.modules.ai.router import usage_router
from app.modules.analysis.router import router as analysis_router
from app.modules.citations.router import router as citations_router
from app.modules.discovery.cache import SearchCache
from app.modules.discovery.gateway import DiscoveryGateway
from app.modules.discovery.providers import (
    ArxivProvider,
    CrossrefProvider,
    OpenAlexProvider,
    PubMedProvider,
    SemanticScholarProvider,
)
from app.modules.discovery.router import router as discovery_router
from app.modules.documents.processing import DocumentProcessor
from app.modules.documents.providers import embedding_provider
from app.modules.documents.queue import DocumentDispatcher
from app.modules.documents.router import router as documents_router
from app.modules.library.cleanup import run_pdf_cleanup
from app.modules.library.router import router as library_router
from app.modules.writing.router import router as writing_router
from app.routers.auth import router as auth_router
from app.routers.papers import router as papers_router
from app.routers.research import router as research_router
from app.routers.users import router as users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    discovery_engine = create_discovery_engine(settings.DATABASE_URL)
    app.state.discovery_session_factory = async_sessionmaker(
        discovery_engine, expire_on_commit=False
    )
    app.state.ai_gateway = AIProviderGateway()
    try:
        # Test database connection
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        logger.info("Connected to PostgreSQL successfully!")
        logger.info("ResearchNest application started.")

    except Exception:
        logger.exception("Database connection failed!")

    redis = (
        Redis.from_url(
            settings.REDIS_URL, socket_connect_timeout=0.5, socket_timeout=0.5
        )
        if settings.REDIS_URL
        else None
    )
    gateway = DiscoveryGateway(
        {
            "arxiv": ArxivProvider(timeout=4),
            "crossref": CrossrefProvider(timeout=4),
            "openalex": OpenAlexProvider(
                timeout=4,
                api_key=(
                    settings.OPENALEX_API_KEY.get_secret_value()
                    if settings.OPENALEX_API_KEY
                    else None
                ),
            ),
            "pubmed": PubMedProvider(
                timeout=4,
                email=settings.PUBMED_TOOL_EMAIL,
                api_key=(
                    settings.PUBMED_API_KEY.get_secret_value()
                    if settings.PUBMED_API_KEY
                    else None
                ),
            ),
            "semantic_scholar": SemanticScholarProvider(
                timeout=4,
                api_key=(
                    settings.SEMANTIC_SCHOLAR_API_KEY.get_secret_value()
                    if settings.SEMANTIC_SCHOLAR_API_KEY
                    else None
                ),
            ),
        },
        cache=SearchCache(redis),
    )
    app.state.discovery_gateway = gateway
    provider = embedding_provider()
    document_dispatcher = DocumentDispatcher(
        app.state.discovery_session_factory,
        DocumentProcessor(app.state.discovery_session_factory, provider),
        redis,
    )
    app.state.document_dispatcher = document_dispatcher
    if settings.APP_ENV != "test" and settings.DOCUMENT_WORKER_IN_API:
        await document_dispatcher.start()
    cleanup_task = (
        asyncio.create_task(run_pdf_cleanup(app.state.discovery_session_factory))
        if settings.APP_ENV != "test"
        else None
    )
    try:
        yield
    finally:
        if cleanup_task:
            cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await cleanup_task
        await document_dispatcher.close()
        if hasattr(provider, "close"):
            provider.close()
        try:
            await gateway.close()
        finally:
            await discovery_engine.dispose()
        logger.info("ResearchNest application stopped.")


app = FastAPI(
    title="ResearchNest API",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-Requested-With",
    ],
)

# Register global exception handlers
register_exception_handlers(app)

# Versioned product API.
for router in (
    research_router,
    papers_router,
    users_router,
    auth_router,
    discovery_router,
    library_router,
    documents_router,
    conversations_router,
    usage_router,
    analysis_router,
    citations_router,
    writing_router,
):
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
