"""Tenant predicates are applied in SQL before analytics materialization."""

from collections import defaultdict
from dataclasses import dataclass, field

from fastapi import HTTPException
from sqlalchemy import and_, func, select

from app.models.analysis import Analysis
from app.models.document_intelligence import DocumentChunk, Embedding
from app.models.library import Document, PaperTag, Tag
from app.models.paper import Author, Paper, PaperAuthor, PaperSource, UserPaper
from app.models.projects import ProjectPaper, ResearchProject
from app.models.research_paper import ResearchPaper
from app.models.writing import Citation
from app.modules.analysis.repository import fingerprint, sources_for_papers

OVERVIEW_PAPER_LIMIT = 5000
GRAPH_PAPER_LIMIT = 300
PROJECT_LIMIT = 1000
FRESHNESS_PAPER_LIMIT = 100
FRESHNESS_CHUNK_LIMIT = 20000


async def require_project(db, owner, project_id):
    if project_id is None:
        return None
    project = await db.scalar(
        select(ResearchProject).where(
            ResearchProject.id == project_id, ResearchProject.user_id == owner
        )
    )
    if project is None:
        raise HTTPException(404, "Project not found.")
    return project


def paper_query(owner, project_id=None):
    statement = (
        select(UserPaper, ResearchPaper, Paper)
        .join(
            ResearchPaper,
            and_(
                ResearchPaper.id == UserPaper.legacy_paper_id,
                ResearchPaper.owner_id == owner,
            ),
        )
        .outerjoin(Paper, Paper.id == UserPaper.paper_id)
        .where(UserPaper.user_id == owner)
    )
    if project_id is not None:
        statement = statement.join(
            ProjectPaper,
            and_(
                ProjectPaper.user_paper_id == UserPaper.id,
                ProjectPaper.user_id == owner,
                ProjectPaper.project_id == project_id,
            ),
        )
    return statement


@dataclass
class LibrarySnapshot:
    rows: list
    total: int
    project_id: int | None
    authors: dict = field(default_factory=dict)
    sources: dict = field(default_factory=dict)
    tags: dict = field(default_factory=dict)
    citations: dict = field(default_factory=dict)
    projects: list = field(default_factory=list)
    memberships: list = field(default_factory=list)
    project_total: int = 0

    @property
    def scope(self):
        return {
            "project_id": self.project_id,
            "total_papers": self.total,
            "included_papers": len(self.rows),
            "truncated": self.total > len(self.rows),
        }

    @property
    def project_scope(self):
        return {
            "total_projects": self.project_total,
            "included_projects": len(self.projects),
            "truncated": self.project_total > len(self.projects),
        }


async def snapshot(db, owner, project_id=None, limit=None):
    await require_project(db, owner, project_id)
    if limit is None:
        limit = OVERVIEW_PAPER_LIMIT
    statement = paper_query(owner, project_id)
    total = await db.scalar(select(func.count()).select_from(statement.subquery()))
    rows = (
        await db.execute(
            statement.order_by(UserPaper.saved_at.desc(), UserPaper.id.desc()).limit(
                limit
            )
        )
    ).all()
    result = LibrarySnapshot(rows, total or 0, project_id)
    ids = [row[0].id for row in rows]
    # Public metadata is only projected through this owner's selected library IDs.
    authors = (
        await db.execute(
            select(UserPaper.id, Author.display_name)
            .join(PaperAuthor, PaperAuthor.paper_id == UserPaper.paper_id)
            .join(Author, Author.id == PaperAuthor.author_id)
            .where(UserPaper.user_id == owner, UserPaper.id.in_(ids))
            .order_by(PaperAuthor.position, Author.id)
        )
    ).all()
    result.authors = defaultdict(list)
    for paper_id, name in authors:
        if name not in result.authors[paper_id]:
            result.authors[paper_id].append(name)
    sources = (
        await db.execute(
            select(UserPaper.id, PaperSource)
            .join(PaperSource, PaperSource.paper_id == UserPaper.paper_id)
            .where(UserPaper.user_id == owner, UserPaper.id.in_(ids))
            .order_by(PaperSource.id)
        )
    ).all()
    result.sources = defaultdict(list)
    for paper_id, source in sources:
        result.sources[paper_id].append(source)
    tags = (
        await db.execute(
            select(PaperTag.user_paper_id, Tag)
            .join(Tag, and_(Tag.id == PaperTag.tag_id, Tag.user_id == owner))
            .where(PaperTag.user_id == owner, PaperTag.user_paper_id.in_(ids))
            .order_by(Tag.id)
        )
    ).all()
    result.tags = defaultdict(list)
    for paper_id, tag in tags:
        result.tags[paper_id].append(tag)
    citations = list(
        await db.scalars(
            select(Citation)
            .where(Citation.user_id == owner, Citation.user_paper_id.in_(ids))
            .order_by(Citation.id)
        )
    )
    result.citations = {c.user_paper_id: c for c in citations if c.is_verified}
    project_statement = select(ResearchProject).where(ResearchProject.user_id == owner)
    if project_id is not None:
        project_statement = project_statement.where(ResearchProject.id == project_id)
    result.project_total = (
        await db.scalar(select(func.count()).select_from(project_statement.subquery()))
        or 0
    )
    result.projects = list(
        await db.scalars(
            project_statement.order_by(ResearchProject.id).limit(PROJECT_LIMIT)
        )
    )
    result.memberships = (
        await db.execute(
            select(ProjectPaper.project_id, ProjectPaper.user_paper_id)
            .join(
                ResearchProject,
                and_(
                    ResearchProject.id == ProjectPaper.project_id,
                    ResearchProject.user_id == owner,
                ),
            )
            .where(
                ProjectPaper.user_id == owner,
                ProjectPaper.user_paper_id.in_(ids),
                ProjectPaper.project_id.in_([p.id for p in result.projects]),
            )
        )
    ).all()
    return result


async def coverage(db, owner, ids):
    # A completed extraction alone is not a usable index: require a current
    # chunk AND an embedding of that same version, all with owner predicates.
    indexed = set(
        await db.scalars(
            select(Document.user_paper_id)
            .join(
                DocumentChunk,
                and_(
                    DocumentChunk.document_id == Document.id,
                    DocumentChunk.user_id == owner,
                    DocumentChunk.document_version == Document.version,
                ),
            )
            .join(
                Embedding,
                and_(
                    Embedding.chunk_id == DocumentChunk.id,
                    Embedding.user_id == owner,
                    Embedding.document_version == Document.version,
                ),
            )
            .where(
                Document.user_id == owner,
                Document.user_paper_id.in_(ids),
                Document.status == "completed",
            )
            .distinct()
        )
    )
    analyses = (
        await db.execute(
            select(Analysis.user_paper_id, Analysis.source_fingerprint)
            .join(
                Document,
                and_(
                    Document.id == Analysis.document_id,
                    Document.user_id == owner,
                    Document.user_paper_id == Analysis.user_paper_id,
                    Document.version == Analysis.document_version,
                    Document.status == "completed",
                ),
            )
            .where(
                Analysis.user_id == owner,
                Analysis.user_paper_id.in_(indexed),
                Analysis.status == "completed",
            )
        )
    ).all()
    # Reuse the same freshness contract as the analysis API, not timestamps or
    # mere presence of an old successful analysis. One source query per paper.
    candidates = defaultdict(list)
    for analysis in analyses:
        candidates[analysis.user_paper_id].append(analysis.source_fingerprint)
    # Count current rows without reading text first, then bound actual text
    # materialization by both papers and rows. The analysis API itself uses a
    # stable first-2000-chunk fingerprint for each current document.
    chunk_counts = dict(
        (
            await db.execute(
                select(Document.user_paper_id, func.count(DocumentChunk.id))
                .join(
                    DocumentChunk,
                    and_(
                        DocumentChunk.document_id == Document.id,
                        DocumentChunk.user_id == owner,
                        DocumentChunk.document_version == Document.version,
                    ),
                )
                .where(
                    Document.user_id == owner,
                    Document.user_paper_id.in_(candidates),
                    Document.status == "completed",
                )
                .group_by(Document.user_paper_id)
            )
        ).all()
    )
    analyzed = set()
    checked = budgeted_rows = 0
    for paper_id, fingerprints in sorted(candidates.items()):
        cost = min(2000, chunk_counts.get(paper_id, 0))
        if checked >= FRESHNESS_PAPER_LIMIT:
            break
        if budgeted_rows + cost > FRESHNESS_CHUNK_LIMIT:
            continue
        checked += 1
        budgeted_rows += cost
        try:
            current = await sources_for_papers(db, owner, [paper_id])
        except HTTPException as error:
            if error.status_code != 409:
                raise
            continue
        if fingerprint(current) in fingerprints:
            analyzed.add(paper_id)
    unchecked = len(candidates) - checked
    return (
        indexed,
        analyzed,
        {
            "checked_papers": checked,
            "unchecked_papers": unchecked,
            "truncated": unchecked > 0,
            "paper_limit": FRESHNESS_PAPER_LIMIT,
            "chunk_limit": FRESHNESS_CHUNK_LIMIT,
            "chunk_rows_budgeted": budgeted_rows,
        },
    )
