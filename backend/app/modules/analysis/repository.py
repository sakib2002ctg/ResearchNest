import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import and_, select

from app.models.analysis import Analysis, ComparisonPaper, PaperComparison
from app.models.document_intelligence import DocumentChunk
from app.models.library import Document
from app.models.paper import UserPaper
from app.models.research_paper import ResearchPaper


@dataclass(frozen=True)
class Source:
    user_paper_id: int
    paper_title: str
    document_id: int
    document_version: int
    file_hash: str
    chunk_id: int
    page_number: int
    section_heading: str | None
    content: str


async def owned_papers(db, owner, paper_ids):
    rows = list(
        await db.scalars(
            select(UserPaper.id).where(
                UserPaper.user_id == owner, UserPaper.id.in_(paper_ids)
            )
        )
    )
    if set(rows) != set(paper_ids):
        raise HTTPException(404, "One or more papers were not found.")


async def sources_for_papers(db, owner, paper_ids):
    await owned_papers(db, owner, paper_ids)
    sources = []
    for paper_id in paper_ids:
        rows = (
            await db.execute(
                select(
                    DocumentChunk,
                    Document.id,
                    Document.version,
                    Document.sha256,
                    ResearchPaper.title,
                )
                .join(
                    Document,
                    and_(
                        Document.id == DocumentChunk.document_id,
                        Document.user_id == owner,
                        Document.version == DocumentChunk.document_version,
                        Document.status == "completed",
                        Document.user_paper_id == paper_id,
                    ),
                )
                .join(
                    UserPaper,
                    and_(
                        UserPaper.id == Document.user_paper_id,
                        UserPaper.user_id == owner,
                    ),
                )
                .join(
                    ResearchPaper,
                    and_(
                        ResearchPaper.id == UserPaper.legacy_paper_id,
                        ResearchPaper.owner_id == owner,
                    ),
                )
                .where(DocumentChunk.user_id == owner)
                .order_by(
                    DocumentChunk.page_number,
                    DocumentChunk.chunk_index,
                    DocumentChunk.id,
                )
                .limit(2000)
            )
        ).all()
        if not rows:
            raise HTTPException(
                409,
                "Upload and finish indexing a PDF for every selected paper "
                "before analysis.",
            )
        sources.extend(
            Source(
                paper_id,
                title,
                doc_id,
                version,
                file_hash,
                chunk.id,
                chunk.page_number,
                chunk.section_heading,
                chunk.content,
            )
            for chunk, doc_id, version, file_hash, title in rows
        )
    return sources


def fingerprint(sources):
    records = [vars(s) for s in sources]
    return hashlib.sha256(
        json.dumps(records, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def versions(sources):
    groups = {}
    for source in sources:
        groups.setdefault(source.user_paper_id, []).append(source)
    return list(
        {
            s.user_paper_id: {
                "user_paper_id": s.user_paper_id,
                "document_id": s.document_id,
                "document_version": s.document_version,
                "file_hash": s.file_hash,
                "source_fingerprint": fingerprint(group),
            }
            for group in groups.values()
            for s in group[:1]
        }.values()
    )


async def saved_analysis(db, owner, paper_id, language):
    await owned_papers(db, owner, [paper_id])
    return await db.scalar(
        select(Analysis).where(
            Analysis.user_id == owner,
            Analysis.user_paper_id == paper_id,
            Analysis.language == language,
        )
    )


async def saved_comparison(db, owner, comparison_id):
    row = await db.scalar(
        select(PaperComparison).where(
            PaperComparison.id == comparison_id, PaperComparison.user_id == owner
        )
    )
    if row is None or not await comparison_access(db, owner, row):
        raise HTTPException(404, "Comparison not found.")
    return row


async def comparison_access(db, owner, row):
    membership = set(
        await db.scalars(
            select(ComparisonPaper.user_paper_id)
            .join(
                UserPaper,
                and_(
                    UserPaper.id == ComparisonPaper.user_paper_id,
                    UserPaper.user_id == owner,
                ),
            )
            .where(
                ComparisonPaper.comparison_id == row.id,
                ComparisonPaper.user_id == owner,
            )
        )
    )
    return membership == set(row.user_paper_ids) and 2 <= len(membership) <= 5


async def analysis_data(db, owner, row):
    # GET retains the owner's snapshot but labels deletion/reindexing as stale.
    try:
        current = await sources_for_papers(db, owner, [row.user_paper_id])
        stale = fingerprint(current) != row.source_fingerprint
    except HTTPException as error:
        if error.status_code != 409:
            raise
        stale = True
    fields = (
        "id",
        "user_paper_id",
        "document_id",
        "document_version",
        "language",
        "status",
        "abstract_summary",
        "research_problem",
        "research_objectives",
        "methodology",
        "datasets",
        "models_and_algorithms",
        "evaluation_metrics",
        "key_results",
        "contributions",
        "limitations",
        "future_work",
        "strengths",
        "weaknesses",
        "field_statuses",
        "evidence_links",
        "error_message",
        "provider_used",
        "model_used",
        "created_at",
        "updated_at",
    )
    return {**{f: serialize_value(getattr(row, f)) for f in fields}, "is_stale": stale}


def serialize_value(value):
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        )
    return value


async def comparison_data(db, owner, row):
    # Private JSON snapshots are only returned after checking relational membership.
    if not await comparison_access(db, owner, row):
        raise HTTPException(404, "Comparison not found.")
    try:
        current = await sources_for_papers(db, owner, row.user_paper_ids)
        stale = versions(current) != row.source_versions
    except HTTPException as error:
        if error.status_code != 409:
            raise
        stale = True
    fields = (
        "id",
        "title",
        "user_paper_ids",
        "language",
        "comparison_matrix",
        "literature_synthesis",
        "research_gaps",
        "evidence_links",
        "provider_used",
        "model_used",
        "created_at",
    )
    return {**{f: serialize_value(getattr(row, f)) for f in fields}, "is_stale": stale}
