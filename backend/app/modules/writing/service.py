from fastapi import HTTPException
from sqlalchemy import delete, select

from app.core.time import utc_now
from app.models.audit_log import AuditLog
from app.models.writing import WritingDocument, WritingVersion
from app.modules.ai.quota import lock_owner
from app.modules.writing.repository import (
    BANGLA_OUTLINES,
    OUTLINES,
    checkpoint,
    document_for_owner,
    references,
    serialize,
    sync_references,
    word_count,
)


def audit(db, owner, action, doc_id):
    db.add(
        AuditLog(
            user_id=owner,
            action=action,
            resource_type="writing_document",
            resource_id=str(doc_id),
        )
    )


async def create(db, owner, body):
    await lock_owner(db, owner)
    refs = await references(db, owner, body.cited_citation_ids, body.content_markdown)
    values = body.model_dump()
    values["outline"] = (
        body.outline
        if body.outline is not None
        else (BANGLA_OUTLINES if body.language == "bn" else OUTLINES)[body.doc_type]
    )
    row = WritingDocument(
        user_id=owner,
        **values,
        word_count=word_count(body.content_markdown),
        revision=1,
        ai_suggestions_log=[],
    )
    db.add(row)
    await db.flush()
    await sync_references(db, owner, row, refs)
    await checkpoint(db, owner, row, "Initial version")
    audit(db, owner, "writing.created", row.id)
    await db.commit()
    return serialize(row)


async def update(db, owner, doc_id, body):
    await lock_owner(db, owner)
    row = await document_for_owner(db, owner, doc_id, lock=True)
    check_revision(row, body.expected_revision)
    values = body.model_dump(
        exclude_unset=True,
        exclude={"create_version", "change_summary", "expected_revision"},
    )
    if any(v is None for v in values.values()):
        raise HTTPException(422, "Editable draft fields cannot be null.")
    content = values.get("content_markdown", row.content_markdown)
    refs = await references(
        db, owner, values.get("cited_citation_ids", row.cited_citation_ids), content
    )
    for key, value in values.items():
        setattr(row, key, value)
    row.word_count, row.revision, row.updated_at = (
        word_count(content),
        row.revision + 1,
        utc_now(),
    )
    await sync_references(db, owner, row, refs)
    if body.create_version:
        await checkpoint(db, owner, row, body.change_summary or "Manual checkpoint")
    audit(db, owner, "writing.saved", doc_id)
    await db.commit()
    return serialize(row)


def check_revision(row, expected):
    if expected is not None and row.revision != expected:
        raise HTTPException(409, "This draft changed elsewhere. Reload before saving.")


async def restore(db, owner, doc_id, version_id, expected):
    await lock_owner(db, owner)
    row = await document_for_owner(db, owner, doc_id, lock=True)
    check_revision(row, expected)
    version = await db.scalar(
        select(WritingVersion).where(
            WritingVersion.user_id == owner,
            WritingVersion.writing_document_id == doc_id,
            WritingVersion.id == version_id,
        )
    )
    if version is None:
        raise HTTPException(404, "Writing version not found.")
    refs = await references(
        db, owner, version.cited_citation_ids, version.content_markdown
    )
    await checkpoint(
        db, owner, row, f"Before restoring version {version.version_number}"
    )
    await db.flush()
    row.title, row.content_markdown, row.outline = (
        version.title,
        version.content_markdown,
        version.outline,
    )
    row.word_count, row.revision, row.updated_at = (
        word_count(row.content_markdown),
        row.revision + 1,
        utc_now(),
    )
    await sync_references(db, owner, row, refs)
    await checkpoint(db, owner, row, f"Restored version {version.version_number}")
    audit(db, owner, "writing.version.restored", doc_id)
    await db.commit()
    return serialize(row)


async def remove(db, owner, doc_id):
    await lock_owner(db, owner)
    await document_for_owner(db, owner, doc_id)
    await db.execute(
        delete(WritingDocument).where(
            WritingDocument.user_id == owner, WritingDocument.id == doc_id
        )
    )
    audit(db, owner, "writing.deleted", doc_id)
    await db.commit()
