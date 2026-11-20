import re
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete, func, select

from app.models.writing import (
    Citation,
    WritingCitation,
    WritingDocument,
    WritingVersion,
)

PLACEHOLDER = re.compile(r"\[@([A-Za-z][A-Za-z0-9_:\-]{0,99})\]")
OUTLINES = {
    "research_paper": [
        "Abstract",
        "Introduction",
        "Literature Review",
        "Methodology",
        "Results and Discussion",
        "Conclusion",
    ],
    "research_proposal": [
        "Introduction",
        "Research Problem",
        "Objectives",
        "Literature Review",
        "Proposed Methodology",
        "Timeline",
    ],
    "thesis": [
        "Abstract",
        "Introduction",
        "Literature Review",
        "Methodology",
        "Results",
        "Discussion",
        "Conclusion",
    ],
    "literature_review": [
        "Introduction",
        "Search Strategy",
        "Thematic Review",
        "Research Gaps",
        "Conclusion",
    ],
}
BANGLA_OUTLINES = {
    "research_paper": [
        "সারসংক্ষেপ",
        "ভূমিকা",
        "সাহিত্য পর্যালোচনা",
        "পদ্ধতি",
        "ফলাফল ও আলোচনা",
        "উপসংহার",
    ],
    "research_proposal": [
        "ভূমিকা",
        "গবেষণার সমস্যা",
        "উদ্দেশ্য",
        "সাহিত্য পর্যালোচনা",
        "প্রস্তাবিত পদ্ধতি",
        "সময়সূচি",
    ],
    "thesis": [
        "সারসংক্ষেপ",
        "ভূমিকা",
        "সাহিত্য পর্যালোচনা",
        "পদ্ধতি",
        "ফলাফল",
        "আলোচনা",
        "উপসংহার",
    ],
    "literature_review": [
        "ভূমিকা",
        "অনুসন্ধান পদ্ধতি",
        "বিষয়ভিত্তিক পর্যালোচনা",
        "গবেষণার সুযোগ",
        "উপসংহার",
    ],
}


def placeholders(text):
    keys = PLACEHOLDER.findall(text)
    if "[@" in PLACEHOLDER.sub("", text):
        raise HTTPException(422, "Invalid citation placeholder. Use [@cite_key].")
    return set(keys)


async def document_for_owner(db, owner, doc_id, *, lock=False):
    query = select(WritingDocument).where(
        WritingDocument.id == doc_id, WritingDocument.user_id == owner
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    row = await db.scalar(query)
    if row is None:
        raise HTTPException(404, "Writing document not found.")
    return row


async def references(db, owner, ids, content):
    ids = set(ids)
    rows = list(
        await db.scalars(
            select(Citation).where(Citation.user_id == owner, Citation.id.in_(ids))
        )
    )
    if {c.id for c in rows} != ids:
        raise HTTPException(404, "One or more references were not found.")
    keys = placeholders(content)
    keyed = list(
        await db.scalars(
            select(Citation).where(
                Citation.user_id == owner, Citation.cite_key.in_(keys)
            )
        )
    )
    if {c.cite_key for c in keyed} != keys:
        raise HTTPException(422, "A citation placeholder has no owned reference.")
    combined = {c.id: c for c in [*rows, *keyed]}
    if len(combined) > 200:
        raise HTTPException(422, "At most 200 references per document.")
    return sorted(combined.values(), key=lambda c: c.id)


async def sync_references(db, owner, document, rows):
    await db.execute(
        delete(WritingCitation).where(
            WritingCitation.user_id == owner,
            WritingCitation.writing_document_id == document.id,
        )
    )
    document.cited_citation_ids = [c.id for c in rows]
    db.add_all(
        WritingCitation(
            user_id=owner, writing_document_id=document.id, citation_id=c.id
        )
        for c in rows
    )


async def checkpoint(db, owner, document, summary):
    number = (
        await db.scalar(
            select(func.max(WritingVersion.version_number)).where(
                WritingVersion.user_id == owner,
                WritingVersion.writing_document_id == document.id,
            )
        )
        or 0
    ) + 1
    row = WritingVersion(
        user_id=owner,
        writing_document_id=document.id,
        version_number=number,
        title=document.title,
        content_markdown=document.content_markdown,
        outline=document.outline,
        cited_citation_ids=document.cited_citation_ids,
        change_summary=summary,
    )
    db.add(row)
    return row


def word_count(content):
    return len(re.findall(r"\S+", PLACEHOLDER.sub("", content)))


def serialize(row):
    fields = (
        "id",
        "doc_type",
        "title",
        "language",
        "outline",
        "content_markdown",
        "cited_citation_ids",
        "ai_suggestions_log",
        "word_count",
        "revision",
        "created_at",
        "updated_at",
    )
    return {f: utc(getattr(row, f)) for f in fields}


def version_data(row):
    fields = (
        "id",
        "writing_document_id",
        "version_number",
        "title",
        "content_markdown",
        "outline",
        "cited_citation_ids",
        "change_summary",
        "created_at",
    )
    return {f: utc(getattr(row, f)) for f in fields}


def utc(value):
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )
    return value
