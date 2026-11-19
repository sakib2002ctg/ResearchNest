import re

from fastapi import HTTPException
from sqlalchemy import and_, select

from app.models.document_intelligence import DocumentChunk
from app.models.library import Document
from app.models.multimodal import AssetChunkLink, AssetExtractionJob, DocumentAsset
from app.modules.writing.repository import utc


async def owned_document(db, owner, doc_id, *, indexed=False, lock=False):
    query = select(Document).where(Document.user_id == owner, Document.id == doc_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = await db.scalar(query)
    if row is None:
        raise HTTPException(404, "Document not found.")
    if indexed and row.status != "completed":
        raise HTTPException(
            409, "Finish indexing the document before extracting assets."
        )
    return row


async def owned_asset(db, owner, asset_id, lock=False):
    query = (
        select(DocumentAsset)
        .join(
            Document,
            and_(
                Document.id == DocumentAsset.document_id,
                Document.user_id == owner,
                Document.version == DocumentAsset.document_version,
                Document.status == "completed",
            ),
        )
        .where(DocumentAsset.id == asset_id, DocumentAsset.user_id == owner)
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = await db.scalar(query)
    if row is None:
        raise HTTPException(404, "Asset not found.")
    return row


async def linked_chunks(db, owner, asset):
    rows = list(
        await db.scalars(
            select(DocumentChunk)
            .join(
                AssetChunkLink,
                and_(
                    AssetChunkLink.chunk_id == DocumentChunk.id,
                    AssetChunkLink.user_id == owner,
                ),
            )
            .where(
                DocumentChunk.user_id == owner,
                DocumentChunk.document_id == asset.document_id,
                DocumentChunk.document_version == asset.document_version,
                AssetChunkLink.asset_id == asset.id,
            )
            .order_by(DocumentChunk.id)
            .limit(20)
        )
    )
    return [
        {
            "id": c.id,
            "page_number": c.page_number,
            "section_heading": c.section_heading,
            "content": c.content[:2000],
        }
        for c in rows
    ]


def asset_data(row):
    fields = (
        "id",
        "document_id",
        "document_version",
        "asset_type",
        "asset_label",
        "page_number",
        "caption",
        "extracted_text_or_latex",
        "structured_data",
        "linked_chunk_ids",
        "ai_explanation",
        "created_at",
        "updated_at",
    )
    return {
        **{f: utc(getattr(row, f)) for f in fields},
        "has_image": row.storage_key is not None,
    }


def job_data(row):
    return {
        "job_id": row.id,
        "document_id": row.document_id,
        "document_version": row.document_version,
        "status": row.status,
        "error_message": row.error_message,
    }


async def list_assets(db, owner, doc_id, asset_type=None, page_number=None):
    doc = await owned_document(db, owner, doc_id)
    query = select(DocumentAsset).where(
        DocumentAsset.user_id == owner,
        DocumentAsset.document_id == doc_id,
        DocumentAsset.document_version == doc.version,
    )
    if asset_type:
        query = query.where(DocumentAsset.asset_type == asset_type)
    if page_number:
        query = query.where(DocumentAsset.page_number == page_number)
    rows = list(
        await db.scalars(
            query.order_by(DocumentAsset.page_number, DocumentAsset.id).limit(200)
        )
    )
    job = await db.scalar(
        select(AssetExtractionJob).where(
            AssetExtractionJob.user_id == owner,
            AssetExtractionJob.document_id == doc_id,
        )
    )
    return {
        "items": [asset_data(row) for row in rows] if doc.status == "completed" else [],
        "extraction": job_data(job) if job else None,
        "is_stale": bool(
            job and (job.document_version != doc.version or doc.status != "completed")
        ),
    }


def match_chunks(asset, chunks):
    label = asset.get("asset_label") or ""
    number = re.search(r"\d+[A-Za-z]?", label)
    if number:
        kind = asset["asset_type"]
        prefix = (
            r"(?:table|টেবিল|সারণি)"
            if kind == "table"
            else (
                r"(?:eq(?:uation)?\.?|সমীকরণ)"
                if kind == "equation"
                else r"(?:fig(?:ure)?\.?|chart|diagram|চিত্র)"
            )
        )
        pattern = re.compile(
            prefix + r"\s*\(?" + re.escape(number.group()) + r"\)?(?!\w)", re.I
        )
        matches = [c.id for c in chunks if pattern.search(c.content)]
        if matches:
            return matches[:20]
    # Without an explicit mention use only the same page as surrounding context.
    return [c.id for c in chunks if c.page_number == asset["page_number"]][:3]
