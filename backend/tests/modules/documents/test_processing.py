import asyncio
from datetime import UTC, datetime, timedelta
from io import BytesIO

import fitz
import pytest
from sqlalchemy import func, select

from app.models.document_intelligence import (
    DocumentChunk,
    DocumentPage,
    Embedding,
    ProcessingJob,
)
from app.models.library import Document
from app.models.paper import UserPaper
from app.models.research_paper import ResearchPaper
from app.models.user import User
from app.modules.documents.embeddings import HashEmbeddingProvider
from app.modules.documents.processing import SAFE_ERROR, DocumentProcessor
from app.modules.library.storage import storage_from_settings

pytestmark = pytest.mark.anyio


def sample_pdf(blank=False):
    document = fitz.open()
    page = document.new_page()
    if not blank:
        page.insert_text(
            (72, 72), "1 Introduction\nResearch text for indexing and retrieval."
        )
    payload = document.tobytes()
    document.close()
    return payload


async def seed(factory, blank=False):
    with BytesIO(sample_pdf(blank)) as source:
        stored = storage_from_settings().store(source, 1)
    async with factory() as db:
        user = User(
            username="researcher",
            email="researcher@example.com",
            hashed_password="test",
        )
        db.add(user)
        await db.flush()
        legacy = ResearchPaper(owner_id=user.id, title="Private research")
        db.add(legacy)
        await db.flush()
        membership = UserPaper(user_id=user.id, legacy_paper_id=legacy.id)
        db.add(membership)
        await db.flush()
        document = Document(
            user_id=user.id,
            user_paper_id=membership.id,
            storage_key=stored.key,
            original_filename="research.pdf",
            size_bytes=stored.size,
            sha256=stored.sha256,
            page_count=1,
        )
        db.add(document)
        await db.flush()
        job = ProcessingJob(
            document_id=document.id, user_id=user.id, document_version=1
        )
        db.add(job)
        await db.commit()
        return user.id, document.id, job.id


async def test_processing_indexes_pages_chunks_embeddings_idempotently(factory):
    owner, document_id, job_id = await seed(factory)
    processor = DocumentProcessor(factory)
    await processor.process_job(job_id)
    await processor.process_job(job_id)
    async with factory() as db:
        document = await db.get(Document, document_id)
        job = await db.get(ProcessingJob, job_id)
        assert document.status == job.status == "completed"
        assert job.attempts == 1
        pages = (await db.scalars(select(DocumentPage))).all()
        chunks = (await db.scalars(select(DocumentChunk))).all()
        vectors = (await db.scalars(select(Embedding))).all()
        assert len(pages) == len(chunks) == len(vectors) == 1
        assert "Research text" in pages[0].raw_text
        assert pages[0].page_number == chunks[0].page_number == 1
        assert vectors[0].user_id == chunks[0].user_id == owner
        assert len(vectors[0].vector_json) == len(vectors[0].vector_pg) == 384


async def test_worker_does_not_accept_a_foreign_owner(factory):
    owner, document_id, job_id = await seed(factory)
    await DocumentProcessor(factory).process_job(job_id, owner_id=owner + 1)
    async with factory() as db:
        assert (await db.get(Document, document_id)).status == "pending"
        assert (await db.get(ProcessingJob, job_id)).attempts == 0


async def test_running_delivery_is_ignored_then_stale_lease_is_reclaimed(factory):
    _, document_id, job_id = await seed(factory)
    async with factory() as db:
        job = await db.get(ProcessingJob, job_id)
        job.status = "running"
        job.started_at = datetime.now(UTC)
        await db.commit()
    processor = DocumentProcessor(factory)
    await processor.process_job(job_id)
    async with factory() as db:
        job = await db.get(ProcessingJob, job_id)
        assert job.attempts == 0
        job.started_at = datetime.now(UTC) - timedelta(hours=1)
        await db.commit()
    await processor.process_job(job_id)
    async with factory() as db:
        assert (await db.get(Document, document_id)).status == "completed"
        assert (await db.get(ProcessingJob, job_id)).attempts == 1


async def test_scanned_page_without_ocr_completes_empty_index(factory, monkeypatch):
    monkeypatch.setattr("app.modules.documents.extractor.shutil.which", lambda _: None)
    _, document_id, job_id = await seed(factory, blank=True)
    await DocumentProcessor(factory).process_job(job_id)
    async with factory() as db:
        assert (await db.get(Document, document_id)).status == "completed"
        assert await db.scalar(select(func.count()).select_from(DocumentPage)) == 1
        assert await db.scalar(select(func.count()).select_from(DocumentChunk)) == 0
        assert await db.scalar(select(func.count()).select_from(Embedding)) == 0


async def test_hash_mismatch_fails_safely_without_partial_index(factory):
    _, document_id, job_id = await seed(factory)
    async with factory() as db:
        document = await db.get(Document, document_id)
        document.sha256 = "f" * 64
        await db.commit()
    await DocumentProcessor(factory).process_job(job_id)
    async with factory() as db:
        assert (await db.get(Document, document_id)).status == "failed"
        assert (await db.get(ProcessingJob, job_id)).last_error == SAFE_ERROR
        assert await db.scalar(select(func.count()).select_from(DocumentPage)) == 0


async def test_version_change_fences_old_worker_before_write(factory):
    owner, document_id, job_id = await seed(factory)

    class ChangedVersion(HashEmbeddingProvider):
        def embed(self, texts):
            import anyio

            anyio.from_thread.run(change_version)
            return super().embed(texts)

    async def change_version():
        async with factory() as db:
            document = await db.get(Document, document_id)
            document.version = 2
            document.status = "pending"
            db.add(
                ProcessingJob(
                    document_id=document_id, user_id=owner, document_version=2
                )
            )
            await db.commit()

    await DocumentProcessor(factory, ChangedVersion()).process_job(job_id)
    async with factory() as db:
        assert (await db.get(Document, document_id)).status == "pending"
        assert await db.scalar(select(func.count()).select_from(DocumentPage)) == 0


async def test_retry_new_version_replaces_old_index(factory):
    owner, document_id, job_id = await seed(factory)
    processor = DocumentProcessor(factory)
    await processor.process_job(job_id)
    async with factory() as db:
        document = await db.get(Document, document_id)
        document.version = 2
        document.status = "pending"
        next_job = ProcessingJob(
            document_id=document_id, user_id=owner, document_version=2
        )
        db.add(next_job)
        await db.commit()
        next_job_id = next_job.id
    await processor.process_job(next_job_id)
    async with factory() as db:
        chunks = (await db.scalars(select(DocumentChunk))).all()
        assert len(chunks) == 1
        assert chunks[0].document_version == 2


async def test_embedding_failure_is_sanitized_and_idempotent(factory):
    _, document_id, job_id = await seed(factory)

    class BrokenProvider(HashEmbeddingProvider):
        def embed(self, texts):
            raise RuntimeError("Secret extracted research text")

    processor = DocumentProcessor(factory, BrokenProvider())
    await processor.process_job(job_id)
    await processor.process_job(job_id)
    async with factory() as db:
        document = await db.get(Document, document_id)
        assert document.status == "failed"
        assert document.error_message == SAFE_ERROR
        assert (await db.get(ProcessingJob, job_id)).attempts == 1
        assert await db.scalar(select(func.count()).select_from(DocumentChunk)) == 0


async def test_simultaneous_job_delivery_only_claims_once(factory):
    owner, document_id, job_id = await seed(factory)
    processor = DocumentProcessor(factory)
    await asyncio.gather(
        processor.process_job(job_id, owner_id=owner),
        processor.process_job(job_id, owner_id=owner),
    )
    async with factory() as db:
        assert (await db.get(Document, document_id)).status == "completed"
        assert (await db.get(ProcessingJob, job_id)).attempts == 1
        assert await db.scalar(select(func.count()).select_from(DocumentPage)) == 1
        assert await db.scalar(select(func.count()).select_from(DocumentChunk)) == 1
        assert await db.scalar(select(func.count()).select_from(Embedding)) == 1
