"""Run the document indexing worker separately from FastAPI."""

import asyncio

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.database.discovery_database import create_discovery_engine
from app.modules.documents.processing import DocumentProcessor
from app.modules.documents.providers import embedding_provider
from app.modules.documents.queue import DocumentDispatcher


async def run() -> None:
    engine = create_discovery_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = (
        Redis.from_url(settings.REDIS_URL, socket_timeout=3, socket_connect_timeout=1)
        if settings.REDIS_URL
        else None
    )
    provider = embedding_provider()
    dispatcher = DocumentDispatcher(
        factory, DocumentProcessor(factory, provider), redis
    )
    try:
        await dispatcher.start()
        await asyncio.Event().wait()
    finally:
        await dispatcher.close()
        if hasattr(provider, "close"):
            provider.close()
        if redis is not None:
            await redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
