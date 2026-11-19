from __future__ import annotations

import hashlib
import hmac
import math
from datetime import UTC, datetime, timedelta

import anyio
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.audit_log import AuditLog
from app.models.document_intelligence import (
    DocumentChunk,
    DocumentPage,
    Embedding,
    ProcessingJob,
)
from app.models.library import Document
from app.modules.documents.chunking import MAX_TOTAL_CHUNKS, make_chunks
from app.modules.documents.embeddings import EmbeddingProvider, HashEmbeddingProvider
from app.modules.documents.extractor import extract_pages_bounded
from app.modules.library.storage import storage_from_settings

SAFE_ERROR = "Document processing failed."
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_EMBEDDING_BATCH = 32
MAX_JOB_ATTEMPTS = 5
JOB_LEASE = timedelta(minutes=10)
PROCESS_TIMEOUT_SECONDS = 180


class DocumentProcessor:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.embedding_provider = embedding_provider or HashEmbeddingProvider()

    async def process_job(self, job_id: int, owner_id: int | None = None) -> None:
        claim_time = datetime.now(UTC)
        eligibility = or_(
            ProcessingJob.status == "queued",
            (ProcessingJob.status == "running")
            & or_(
                ProcessingJob.started_at.is_(None),
                ProcessingJob.started_at <= claim_time - JOB_LEASE,
            ),
        )
        async with self.session_factory() as db:
            filters = (
                (ProcessingJob.user_id == owner_id,) if owner_id is not None else ()
            )
            locator = (
                await db.execute(
                    select(ProcessingJob.document_id, ProcessingJob.user_id).where(
                        ProcessingJob.id == job_id, *filters
                    )
                )
            ).one_or_none()
            if locator is None:
                return
            document_id, owner_id = locator
            document = await db.scalar(
                select(Document)
                .where(Document.id == document_id, Document.user_id == owner_id)
                .with_for_update()
            )
            if document is None:
                return
            related_job = (
                ProcessingJob.id == job_id,
                ProcessingJob.user_id == owner_id,
                ProcessingJob.document_id == document_id,
                ProcessingJob.job_type == "pdf_extract_and_index",
                eligibility,
            )
            attempt = await db.scalar(
                update(ProcessingJob)
                .where(
                    *related_job,
                    ProcessingJob.document_version == document.version,
                    ProcessingJob.attempts < MAX_JOB_ATTEMPTS,
                )
                .values(
                    status="running",
                    attempts=ProcessingJob.attempts + 1,
                    started_at=claim_time,
                    completed_at=None,
                    last_error=None,
                )
                .returning(ProcessingJob.attempts)
            )
            if attempt is None:
                failed_version = await db.scalar(
                    update(ProcessingJob)
                    .where(
                        *related_job,
                        or_(
                            ProcessingJob.document_version != document.version,
                            ProcessingJob.attempts >= MAX_JOB_ATTEMPTS,
                        ),
                    )
                    .values(
                        status="failed", last_error=SAFE_ERROR, completed_at=claim_time
                    )
                    .returning(ProcessingJob.document_version)
                )
                if failed_version == document.version:
                    document.status = "failed"
                    document.error_message = SAFE_ERROR
                await db.commit()
                return
            document.status = "processing"
            document.error_message = None
            document.updated_at = claim_time
            await db.commit()

        try:
            with anyio.fail_after(PROCESS_TIMEOUT_SECONDS):
                await self._extract_index_finalize(
                    job_id, document_id, owner_id, attempt
                )
        except Exception:
            # Never log parser/provider exceptions; these may contain extracted text.
            await self._fail(job_id, document_id, owner_id, attempt)

    async def _extract_index_finalize(
        self, job_id: int, document_id: int, owner_id: int, attempt: int
    ) -> None:
        async with self.session_factory() as db:
            job = await db.scalar(
                select(ProcessingJob).where(
                    ProcessingJob.id == job_id, ProcessingJob.user_id == owner_id
                )
            )
            if job is None or job.status != "running" or job.attempts != attempt:
                return
            document = await db.scalar(
                select(Document).where(
                    Document.id == job.document_id,
                    Document.user_id == job.user_id,
                    Document.version == job.document_version,
                )
            )
            if document is None or document.status != "processing":
                return
            owner_id = document.user_id
            document_id = document.id
            version = document.version
            storage_key = document.storage_key
            expected_size = document.size_bytes
            expected_pages = document.page_count
            file_hash = document.file_hash

        def read_pdf() -> bytes:
            if not 0 < expected_size <= MAX_DOCUMENT_BYTES:
                raise ValueError(SAFE_ERROR)
            with storage_from_settings().open(storage_key, expected_size) as stream:
                payload = stream.read(MAX_DOCUMENT_BYTES + 1)
            if len(payload) != expected_size or not hmac.compare_digest(
                hashlib.sha256(payload).hexdigest(), file_hash
            ):
                raise ValueError(SAFE_ERROR)
            return payload

        pages = await anyio.to_thread.run_sync(
            lambda: extract_pages_bounded(read_pdf())
        )
        if len(pages) != expected_pages or not pages:
            raise ValueError(SAFE_ERROR)
        chunks = await anyio.to_thread.run_sync(make_chunks, pages)
        if len(chunks) > MAX_TOTAL_CHUNKS:
            raise ValueError(SAFE_ERROR)
        vectors = []
        for start in range(0, len(chunks), MAX_EMBEDDING_BATCH):
            batch = [
                chunk.content for chunk in chunks[start : start + MAX_EMBEDDING_BATCH]
            ]
            vectors.extend(
                await anyio.to_thread.run_sync(self.embedding_provider.embed, batch)
            )
        self._validate_vectors(vectors, len(chunks), self.embedding_provider.dimension)
        if chunks and self.embedding_provider.dimension != 384:
            raise ValueError(SAFE_ERROR)

        async with self.session_factory() as db:
            document = await db.scalar(
                select(Document)
                .where(Document.id == document_id, Document.user_id == owner_id)
                .with_for_update()
            )
            job = await db.scalar(
                select(ProcessingJob)
                .where(ProcessingJob.id == job_id, ProcessingJob.user_id == owner_id)
                .with_for_update()
            )
            if (
                job is None
                or document is None
                or job.status != "running"
                or job.attempts != attempt
                or job.document_version != version
                or document.version != version
                or document.status != "processing"
            ):
                return

            # Replace prior versions atomically; chunks cascade to their vectors.
            await db.execute(
                delete(DocumentChunk).where(
                    DocumentChunk.document_id == document_id,
                    DocumentChunk.user_id == owner_id,
                )
            )
            await db.execute(
                delete(DocumentPage).where(
                    DocumentPage.document_id == document_id,
                    DocumentPage.user_id == owner_id,
                )
            )

            db.add_all(
                DocumentPage(
                    document_id=document_id,
                    user_id=owner_id,
                    document_version=version,
                    page_number=page.page_number,
                    raw_text=page.raw_text,
                    ocr_used=page.ocr_used,
                    section_heading=page.section_heading,
                )
                for page in pages
            )
            db.add_all(
                DocumentChunk(
                    document_id=document_id,
                    user_id=owner_id,
                    document_version=version,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    section_heading=chunk.section_heading,
                    content=chunk.content,
                    token_count=chunk.token_count,
                )
                for chunk in chunks
            )
            await db.flush()
            persisted = (
                await db.scalars(
                    select(DocumentChunk)
                    .where(
                        DocumentChunk.document_id == document_id,
                        DocumentChunk.document_version == version,
                        DocumentChunk.user_id == owner_id,
                    )
                    .order_by(DocumentChunk.page_number, DocumentChunk.chunk_index)
                )
            ).all()
            if len(persisted) != len(vectors):
                raise ValueError(SAFE_ERROR)

            db.add_all(
                Embedding(
                    chunk_id=chunk.id,
                    user_id=owner_id,
                    document_version=version,
                    model_name=self.embedding_provider.model_name,
                    vector_json=vector,
                    vector_pg=vector,
                )
                for chunk, vector in zip(persisted, vectors, strict=True)
            )
            document.status = "completed"
            document.error_message = None
            document.updated_at = datetime.now(UTC)
            job.status = "completed"
            job.last_error = None
            job.completed_at = datetime.now(UTC)
            db.add(
                AuditLog(
                    user_id=owner_id,
                    action="document.index.completed",
                    resource_type="document",
                    resource_id=str(document_id),
                    details={"version": version},
                )
            )
            await db.commit()

    async def _fail(
        self, job_id: int, document_id: int, owner_id: int, attempt: int
    ) -> None:
        async with self.session_factory() as db:
            document = await db.scalar(
                select(Document)
                .where(Document.id == document_id, Document.user_id == owner_id)
                .with_for_update()
            )
            job = await db.scalar(
                select(ProcessingJob)
                .where(ProcessingJob.id == job_id, ProcessingJob.user_id == owner_id)
                .with_for_update()
            )
            if job is None or job.status != "running" or job.attempts != attempt:
                return
            if document is not None and document.version == job.document_version:
                document.status = "failed"
                document.error_message = SAFE_ERROR
                document.updated_at = datetime.now(UTC)
            job.status = "failed"
            job.last_error = SAFE_ERROR
            job.completed_at = datetime.now(UTC)
            if document is not None:
                db.add(
                    AuditLog(
                        user_id=owner_id,
                        action="document.index.failed",
                        resource_type="document",
                        resource_id=str(document_id),
                        details={"version": job.document_version},
                    )
                )
            await db.commit()

    @staticmethod
    def _validate_vectors(
        vectors: list[list[float]], expected_count: int, expected_dimension: int
    ) -> None:
        if len(vectors) != expected_count:
            raise ValueError(SAFE_ERROR)
        for vector in vectors:
            if len(vector) != expected_dimension:
                raise ValueError(SAFE_ERROR)
            if not all(math.isfinite(value) for value in vector):
                raise ValueError(SAFE_ERROR)
