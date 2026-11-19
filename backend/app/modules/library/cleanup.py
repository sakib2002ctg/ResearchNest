import asyncio

import anyio
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.library import Document, PDFDeletion
from app.models.paper import UserPaper


def queue_owned_pdfs(
    db: Session, owner_id: int, legacy_paper_id: int | None = None
) -> None:
    """Enqueue objects in the same transaction as the owner or paper deletion."""
    query = select(Document.storage_key).where(Document.user_id == owner_id)
    if legacy_paper_id is not None:
        query = query.join(
            UserPaper,
            (UserPaper.user_id == Document.user_id)
            & (UserPaper.id == Document.user_paper_id),
        ).where(UserPaper.legacy_paper_id == legacy_paper_id)
    db.add_all(PDFDeletion(storage_key=key) for key in db.scalars(query))


async def drain_pdf_deletions(db: AsyncSession) -> None:
    from app.modules.library.storage import storage_from_settings

    try:
        pending = (
            await db.scalars(
                select(PDFDeletion)
                .order_by(PDFDeletion.created_at, PDFDeletion.storage_key)
                .limit(50)
                .with_for_update(skip_locked=True)
            )
        ).all()
        if pending:
            storage = storage_from_settings()
            for entry in pending:
                try:
                    await anyio.to_thread.run_sync(storage.remove, entry.storage_key)
                except OSError:
                    logger.warning("PDF object cleanup could not finish. Will retry.")
                else:
                    await db.delete(entry)
        await db.commit()
    except (OSError, SQLAlchemyError):
        await db.rollback()
        logger.warning("PDF cleanup could not finish. Will retry.")


async def run_pdf_cleanup(factory: async_sessionmaker[AsyncSession]) -> None:
    while True:
        await asyncio.sleep(30)
        async with factory() as db:
            await drain_pdf_deletions(db)
