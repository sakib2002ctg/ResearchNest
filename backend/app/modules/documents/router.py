from __future__ import annotations

from datetime import UTC, datetime
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.discovery_database import get_discovery_db
from app.models.audit_log import AuditLog
from app.models.document_intelligence import DocumentPage, ProcessingJob
from app.models.library import Document
from app.modules.documents.dependencies import DocumentID, private_response
from app.modules.library.dependencies import get_library_owner

router = APIRouter(
    prefix="/documents", tags=["documents"], dependencies=[Depends(private_response)]
)


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_paper_id: int
    page_count: int
    status: str
    version: int


class JobStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    attempts: int
    last_error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    document_version: int


class DocumentStatus(BaseModel):
    document_id: int
    status: str
    version: int
    jobs: list[JobStatus]


class PageResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    page_number: int
    raw_text: str
    ocr_used: bool
    section_heading: str | None


class PageResults(BaseModel):
    items: list[PageResult]
    page: int
    size: int
    total: int
    pages: int


async def _document(db: AsyncSession, owner: int, document_id: int) -> Document:
    document = await db.scalar(
        select(Document).where(Document.id == document_id, Document.user_id == owner)
    )
    if document is None:
        raise HTTPException(404, "Document not found.")
    return document


@router.get("/{document_id}")
async def metadata(
    document_id: DocumentID,
    owner: int = Depends(get_library_owner),
    db: AsyncSession = Depends(get_discovery_db),
) -> DocumentMetadata:
    return DocumentMetadata.model_validate(await _document(db, owner, document_id))


@router.get("/{document_id}/status")
async def status(
    document_id: DocumentID,
    owner: int = Depends(get_library_owner),
    db: AsyncSession = Depends(get_discovery_db),
) -> DocumentStatus:
    document = await _document(db, owner, document_id)
    jobs = (
        await db.scalars(
            select(ProcessingJob)
            .where(
                ProcessingJob.document_id == document.id,
                ProcessingJob.user_id == owner,
            )
            .order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc())
            .limit(10)
        )
    ).all()
    return DocumentStatus(
        document_id=document.id,
        status=document.status,
        version=document.version,
        jobs=[JobStatus.model_validate(job) for job in jobs],
    )


@router.get("/{document_id}/pages")
async def pages(
    document_id: DocumentID,
    page: int = Query(1, ge=1, le=100000),
    size: int = Query(10, ge=1, le=50),
    owner: int = Depends(get_library_owner),
    db: AsyncSession = Depends(get_discovery_db),
) -> PageResults:
    document = await _document(db, owner, document_id)
    base = select(DocumentPage).where(
        DocumentPage.document_id == document.id,
        DocumentPage.user_id == owner,
        DocumentPage.document_version == document.version,
    )
    total = await db.scalar(select(func.count()).select_from(base.subquery())) or 0
    items = (
        await db.scalars(
            base.order_by(DocumentPage.page_number)
            .offset((page - 1) * size)
            .limit(size)
        )
    ).all()
    return PageResults(
        items=[PageResult.model_validate(item) for item in items],
        page=page,
        size=size,
        total=total,
        pages=ceil(total / size) if total else 0,
    )


@router.post("/{document_id}/retry")
async def retry(
    document_id: DocumentID,
    request: Request,
    owner: int = Depends(get_library_owner),
    db: AsyncSession = Depends(get_discovery_db),
) -> DocumentStatus:
    document = await db.scalar(
        select(Document)
        .where(Document.id == document_id, Document.user_id == owner)
        .with_for_update()
    )
    if document is None:
        raise HTTPException(404, "Document not found.")
    if document.status != "failed":
        raise HTTPException(409, "Document is already being processed.")
    document.version += 1
    document.status = "pending"
    document.error_message = None
    document.updated_at = datetime.now(UTC)
    job = ProcessingJob(
        document_id=document.id,
        user_id=owner,
        document_version=document.version,
    )
    db.add(job)
    db.add(
        AuditLog(
            user_id=owner,
            action="document.index.retry",
            resource_type="document",
            resource_id=str(document.id),
            details={"version": document.version},
        )
    )
    await db.commit()
    await db.refresh(document)
    await db.refresh(job)
    await request.app.state.document_dispatcher.enqueue(job.id)
    return DocumentStatus(
        document_id=document.id,
        status=document.status,
        version=document.version,
        jobs=[JobStatus.model_validate(job)],
    )
