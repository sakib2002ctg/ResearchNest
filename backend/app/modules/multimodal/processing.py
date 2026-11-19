import asyncio
import hashlib
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import delete, or_, select, update

from app.core.time import utc_now
from app.models.audit_log import AuditLog
from app.models.document_intelligence import DocumentChunk
from app.models.multimodal import (
    AssetChunkLink,
    AssetDeletion,
    AssetExtractionJob,
    DocumentAsset,
)
from app.modules.ai.quota import lock_owner
from app.modules.library.storage import MAX_PDF_BYTES, storage_from_settings
from app.modules.multimodal.cleanup import drain_asset_deletions
from app.modules.multimodal.extractor import extract_assets_bounded
from app.modules.multimodal.repository import job_data, match_chunks, owned_document
from app.modules.multimodal.storage import AssetStorage


async def request_extraction(db, owner, doc_id):
    await lock_owner(db, owner)
    doc = await owned_document(db, owner, doc_id, indexed=True, lock=True)
    job = await db.scalar(
        select(AssetExtractionJob)
        .where(
            AssetExtractionJob.user_id == owner,
            AssetExtractionJob.document_id == doc_id,
        )
        .with_for_update()
    )
    if (
        job
        and job.status in {"queued", "running"}
        and job.document_version == doc.version
    ):
        return job_data(job)
    if job is None:
        job = AssetExtractionJob(
            user_id=owner,
            document_id=doc_id,
            document_version=doc.version,
            generation=1,
            status="queued",
            attempts=0,
        )
        db.add(job)
    else:
        job.generation += 1
        job.document_version = doc.version
        job.status = "queued"
        job.attempts = 0
        job.started_at = None
        job.completed_at = None
        job.error_message = None
    db.add(
        AuditLog(
            user_id=owner,
            action="multimodal.extraction.requested",
            resource_type="document",
            resource_id=str(doc_id),
        )
    )
    await db.commit()
    return job_data(job)


class AssetProcessor:
    def __init__(self, factory, extractor=extract_assets_bounded):
        self.factory, self.extractor = factory, extractor

    async def process_job(self, job_id):
        async with self.factory() as db:
            locator = (
                await db.execute(
                    select(
                        AssetExtractionJob.user_id, AssetExtractionJob.document_id
                    ).where(AssetExtractionJob.id == job_id)
                )
            ).one_or_none()
            if not locator:
                return
            owner, doc_id = locator
            try:
                doc = await owned_document(db, owner, doc_id, lock=True)
            except HTTPException:
                return
            job = await db.scalar(
                select(AssetExtractionJob)
                .where(
                    AssetExtractionJob.id == job_id, AssetExtractionJob.user_id == owner
                )
                .with_for_update()
            )
            if job is None or job.status in {"completed", "failed"}:
                return
            if doc.status != "completed":
                job.status = "failed"
                job.error_message = "Document is no longer indexed."
                await db.commit()
                return
            if (
                job.status == "running"
                and job.started_at
                and job.started_at.replace(tzinfo=utc_now().tzinfo)
                > utc_now() - timedelta(minutes=3)
            ):
                return
            if job.document_version != doc.version or job.attempts >= 3:
                job.status = "failed"
                job.error_message = (
                    "Document changed or attempts exceeded. Retry extraction."
                )
                await db.commit()
                return
            job.status = "running"
            job.attempts += 1
            job.started_at = utc_now()
            attempt, generation, version = job.attempts, job.generation, doc.version
            key, size, checksum = doc.storage_key, doc.size_bytes, doc.sha256
            await db.commit()
        saved = []
        try:

            def read():
                if size > MAX_PDF_BYTES:
                    raise ValueError("PDF too large.")
                with storage_from_settings().open(key, size) as stream:
                    data = stream.read(size)
                if hashlib.sha256(data).hexdigest() != checksum:
                    raise ValueError("PDF changed.")
                return data

            data = await asyncio.to_thread(read)
            async with asyncio.timeout(75):
                assets = await asyncio.to_thread(self.extractor, data)
            if len(assets) > 200:
                raise ValueError("Too many assets.")
            storage = AssetStorage(owner)
            for asset in assets:
                image = asset.pop("image_bytes", None)
                asset["storage_key"] = None
                asset["image_size_bytes"] = len(image) if image else None
                if image:
                    new_key = storage.allocate_key()
                    # Recover in-flight writes even when the caller is canceled.
                    async with self.factory() as intent_db:
                        intent_db.add(
                            AssetDeletion(
                                user_id=owner,
                                storage_key=new_key,
                                created_at=utc_now() + timedelta(minutes=5),
                            )
                        )
                        await intent_db.commit()
                    saved.append(new_key)
                    await asyncio.to_thread(storage.save, image, new_key)
                    asset["storage_key"] = new_key
            async with self.factory() as db:
                doc = await owned_document(db, owner, doc_id, indexed=True, lock=True)
                job = await db.scalar(
                    select(AssetExtractionJob)
                    .where(
                        AssetExtractionJob.user_id == owner,
                        AssetExtractionJob.id == job_id,
                    )
                    .with_for_update()
                )
                if (
                    job is None
                    or job.status != "running"
                    or job.generation != generation
                    or job.attempts != attempt
                    or doc.version != version
                ):
                    raise ValueError("Stale extraction attempt.")
                chunks = list(
                    await db.scalars(
                        select(DocumentChunk)
                        .where(
                            DocumentChunk.user_id == owner,
                            DocumentChunk.document_id == doc_id,
                            DocumentChunk.document_version == version,
                        )
                        .order_by(DocumentChunk.id)
                    )
                )
                await db.execute(
                    delete(DocumentAsset).where(
                        DocumentAsset.user_id == owner,
                        DocumentAsset.document_id == doc_id,
                    )
                )
                for asset in assets:
                    ids = match_chunks(asset, chunks)
                    row = DocumentAsset(
                        user_id=owner,
                        document_id=doc_id,
                        document_version=version,
                        extraction_generation=generation,
                        linked_chunk_ids=ids,
                        **asset,
                    )
                    db.add(row)
                    await db.flush()
                    db.add_all(
                        AssetChunkLink(user_id=owner, asset_id=row.id, chunk_id=cid)
                        for cid in ids
                    )
                job.status = "completed"
                job.completed_at = utc_now()
                job.error_message = None
                db.add(
                    AuditLog(
                        user_id=owner,
                        action="multimodal.extraction.completed",
                        resource_type="document",
                        resource_id=str(doc_id),
                        details={"asset_count": len(assets)},
                    )
                )
                await db.execute(
                    delete(AssetDeletion).where(
                        AssetDeletion.user_id == owner,
                        AssetDeletion.storage_key.in_(saved),
                    )
                )
                await db.commit()
                saved = []
                await drain_asset_deletions(db)
        except asyncio.CancelledError:
            # Delayed cleanup intents survive shutdown and retain known object keys.
            raise
        except Exception:
            async with self.factory() as db:
                job = await db.scalar(
                    select(AssetExtractionJob).where(
                        AssetExtractionJob.id == job_id,
                        AssetExtractionJob.user_id == owner,
                        AssetExtractionJob.generation == generation,
                        AssetExtractionJob.attempts == attempt,
                    )
                )
                if job:
                    job.status = "failed"
                    job.error_message = "Asset extraction failed. Please retry."
                    db.add(
                        AuditLog(
                            user_id=owner,
                            action="multimodal.extraction.failed",
                            resource_type="document",
                            resource_id=str(doc_id),
                        )
                    )
                await db.execute(
                    update(AssetDeletion)
                    .where(
                        AssetDeletion.user_id == owner,
                        AssetDeletion.storage_key.in_(saved),
                    )
                    .values(created_at=utc_now())
                )
                await db.commit()
                await drain_asset_deletions(db)


async def run_jobs(factory):
    processor = AssetProcessor(factory)
    while True:
        try:
            async with factory() as db:
                jobs = list(
                    await db.scalars(
                        select(AssetExtractionJob.id)
                        .where(
                            or_(
                                AssetExtractionJob.status == "queued",
                                (AssetExtractionJob.status == "running")
                                & or_(
                                    AssetExtractionJob.started_at.is_(None),
                                    AssetExtractionJob.started_at
                                    <= utc_now() - timedelta(minutes=3),
                                ),
                            )
                        )
                        .order_by(AssetExtractionJob.created_at)
                        .limit(20)
                    )
                )
            for job in jobs:
                await processor.process_job(job)
        except Exception:
            pass  # failures contain no document text or parser details in logs
        await asyncio.sleep(2)
