"""Separate extraction worker: python -m app.modules.multimodal.worker."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import settings
from app.database.discovery_database import create_discovery_engine
from app.modules.multimodal.cleanup import run_asset_cleanup
from app.modules.multimodal.processing import run_jobs


async def run():
    engine = create_discovery_engine(settings.DATABASE_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        await asyncio.gather(run_jobs(factory), run_asset_cleanup(factory))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
