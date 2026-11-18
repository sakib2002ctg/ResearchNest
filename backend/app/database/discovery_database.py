"""Async persistence dependency used by the discovery request paths."""

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy import event
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _async_database_url(url: str) -> URL:
    parsed = make_url(url)
    backend = parsed.get_backend_name()
    driver = {"postgresql": "asyncpg", "sqlite": "aiosqlite"}.get(backend)
    if driver is None:
        raise ValueError(f"Discovery async sessions do not support {backend!r}.")
    return parsed.set(drivername=f"{backend}+{driver}")


def create_discovery_engine(url: str) -> AsyncEngine:
    """Create an async engine from the configured synchronous application URL."""
    async_url = _async_database_url(url)
    engine = create_async_engine(async_url, pool_pre_ping=True)
    if async_url.get_backend_name() == "sqlite":

        @event.listens_for(engine.sync_engine, "connect")
        def enable_foreign_keys(connection, _):
            cursor = connection.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

    return engine


async def get_discovery_db(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = (
        request.app.state.discovery_session_factory
    )
    async with factory() as session:
        yield session
