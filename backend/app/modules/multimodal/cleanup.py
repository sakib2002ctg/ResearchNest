import asyncio

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import logger
from app.core.time import utc_now
from app.models.multimodal import AssetDeletion
from app.modules.multimodal.storage import AssetStorage


async def drain_asset_deletions(db):
    try:
        pending = list(
            await db.scalars(
                select(AssetDeletion)
                .where(AssetDeletion.created_at <= utc_now())
                .order_by(AssetDeletion.created_at)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
        )
        for entry in pending:
            try:
                await asyncio.to_thread(
                    AssetStorage(entry.user_id).remove, entry.storage_key
                )
            except OSError:
                logger.warning("Private asset cleanup will retry.")
            else:
                await db.delete(entry)
        await db.commit()
    except (OSError, SQLAlchemyError):
        await db.rollback()
        logger.warning("Private asset cleanup will retry.")


async def run_asset_cleanup(factory):
    while True:
        await asyncio.sleep(30)
        async with factory() as db:
            await drain_asset_deletions(db)
