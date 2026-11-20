"""All private reads constrain the authenticated owner in SQL."""

import re
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import and_, func, select

from app.models.analysis import Analysis
from app.models.assistant import Conversation, Message
from app.models.library import Collection
from app.models.paper import Author, Paper, PaperAuthor, UserPaper
from app.models.projects import ProjectPaper, ProjectTask, ResearchNote, ResearchProject
from app.models.research_paper import ResearchPaper
from app.models.writing import Citation
from app.modules.analysis.repository import analysis_data
from app.modules.citations.formatter import format_citations

PROJECT_FIELDS = (
    "id",
    "title",
    "description",
    "objectives",
    "status",
    "progress_percent",
    "revision",
    "target_deadline",
    "collection_id",
    "created_at",
    "updated_at",
)
NOTE_FIELDS = (
    "id",
    "project_id",
    "user_paper_id",
    "title",
    "content",
    "created_at",
    "updated_at",
)
TASK_FIELDS = (
    "id",
    "project_id",
    "title",
    "description",
    "is_milestone",
    "status",
    "due_date",
    "completed_at",
    "created_at",
    "updated_at",
)
CONVERSATION_FIELDS = ("id", "title", "language", "created_at", "updated_at")


def fields(row, names):
    return {name: getattr(row, name) for name in names}


async def owned_project(db, owner, project_id):
    row = await db.scalar(
        select(ResearchProject).where(
            ResearchProject.id == project_id, ResearchProject.user_id == owner
        )
    )
    if row is None:
        raise HTTPException(404, "Project not found.")
    return row


async def owned_resource(db, owner, model, resource_id, project_id=None):
    query = select(model).where(model.id == resource_id, model.user_id == owner)
    if project_id is not None:
        query = query.where(model.project_id == project_id)
    row = await db.scalar(query)
    if row is None:
        raise HTTPException(404, "Resource not found.")
    return row


async def validate_collection(db, owner, collection_id):
    if collection_id is not None:
        await owned_resource(db, owner, Collection, collection_id)


async def validate_paper(db, owner, paper_id):
    if paper_id is not None:
        await owned_resource(db, owner, UserPaper, paper_id)


async def notes(db, owner, project_id):
    return list(
        await db.scalars(
            select(ResearchNote)
            .where(ResearchNote.user_id == owner, ResearchNote.project_id == project_id)
            .order_by(ResearchNote.created_at, ResearchNote.id)
        )
    )


async def tasks(db, owner, project_id):
    return list(
        await db.scalars(
            select(ProjectTask)
            .where(ProjectTask.user_id == owner, ProjectTask.project_id == project_id)
            .order_by(ProjectTask.created_at, ProjectTask.id)
        )
    )


async def papers(db, owner, project_id):
    rows = (
        await db.execute(
            select(ProjectPaper, UserPaper, ResearchPaper, Paper)
            .join(
                UserPaper,
                and_(
                    UserPaper.id == ProjectPaper.user_paper_id,
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
            .outerjoin(Paper, Paper.id == UserPaper.paper_id)
            .where(ProjectPaper.user_id == owner, ProjectPaper.project_id == project_id)
            .order_by(ProjectPaper.added_at, ProjectPaper.id)
        )
    ).all()
    return rows


def paper_data(row):
    link, user_paper, legacy, canonical = row
    return {
        "id": link.id,
        "user_paper_id": user_paper.id,
        "paper_id": user_paper.paper_id,
        "title": legacy.title,
        "authors": legacy.authors,
        "abstract": legacy.abstract,
        "source": legacy.source,
        "url": legacy.url,
        "doi": canonical.doi if canonical else None,
        "role_in_project": link.role_in_project,
        "added_at": link.added_at,
        "reading_status": user_paper.reading_status,
    }


async def conversations(db, owner, project_id):
    return list(
        await db.scalars(
            select(Conversation)
            .where(Conversation.user_id == owner, Conversation.project_id == project_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        )
    )


async def project_data(db, owner, row, detail=False):
    task_rows = await tasks(db, owner, row.id)
    paper_rows = await papers(db, owner, row.id)
    result = {
        **fields(row, PROJECT_FIELDS),
        "paper_count": len(paper_rows),
        "task_count": len(task_rows),
        "completed_task_count": sum(task.status == "done" for task in task_rows),
    }
    if detail:
        result.update(
            papers=[paper_data(paper) for paper in paper_rows],
            notes=[
                fields(note, NOTE_FIELDS) for note in await notes(db, owner, row.id)
            ],
            tasks=[fields(task, TASK_FIELDS) for task in task_rows],
            conversations=[
                fields(item, CONVERSATION_FIELDS)
                for item in await conversations(db, owner, row.id)
            ],
        )
    return result


async def list_projects(db, owner, status, limit, offset):
    query = select(ResearchProject).where(ResearchProject.user_id == owner)
    if status is not None:
        query = query.where(ResearchProject.status == status)
    rows = list(
        await db.scalars(
            query.order_by(ResearchProject.updated_at.desc(), ResearchProject.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return [await project_data(db, owner, row) for row in rows]


async def recompute_progress(db, owner, project):
    await db.flush()
    total = await db.scalar(
        select(func.count(ProjectTask.id)).where(
            ProjectTask.user_id == owner, ProjectTask.project_id == project.id
        )
    )
    done = await db.scalar(
        select(func.count(ProjectTask.id)).where(
            ProjectTask.user_id == owner,
            ProjectTask.project_id == project.id,
            ProjectTask.status == "done",
        )
    )
    project.progress_percent = round(done * 100 / total, 2) if total else 0
    if project.status != "archived":
        if total and total == done:
            project.status = "completed"
        elif project.status == "completed":
            project.status = "active"


async def export_data(db, owner, project, style):
    result = await project_data(db, owner, project, detail=True)
    source_rows = await papers(db, owner, project.id)
    paper_ids = [row[1].id for row in source_rows]
    citation_rows = list(
        await db.scalars(
            select(Citation)
            .where(Citation.user_id == owner, Citation.user_paper_id.in_(paper_ids))
            .order_by(Citation.id)
        )
    )
    by_paper = {row.user_paper_id: row for row in citation_rows}
    author_rows = (
        await db.execute(
            select(UserPaper.id, Author.display_name)
            .join(PaperAuthor, PaperAuthor.paper_id == UserPaper.paper_id)
            .join(Author, Author.id == PaperAuthor.author_id)
            .where(UserPaper.user_id == owner, UserPaper.id.in_(paper_ids))
            .order_by(PaperAuthor.position, Author.id)
        )
    ).all()
    canonical_authors = {}
    for paper_id, name in author_rows:
        canonical_authors.setdefault(paper_id, []).append(name)
    references = []
    for _, item, legacy, canonical in source_rows:
        if item.id in by_paper:
            references.append(by_paper[item.id])
            continue
        references.append(
            SimpleNamespace(
                id=None,
                cite_key=f"paper-{item.id}",
                title=legacy.title,
                authors=canonical_authors.get(item.id)
                or [
                    name.strip()
                    for name in re.split(r";|\s+and\s+", legacy.authors or "")
                    if name.strip()
                ],
                year=(
                    canonical.publication_date.year
                    if canonical and canonical.publication_date
                    else None
                ),
                doi=canonical.doi if canonical else None,
                url=legacy.url,
                venue=None,
                publisher=None,
                volume=None,
                issue=None,
                pages=None,
                entry_type="article",
                is_verified=False,
            )
        )
    result["bibliography"] = format_citations(references, style)
    # Summaries belong to the owner and are limited to linked library papers.
    summaries = list(
        await db.scalars(
            select(Analysis)
            .where(
                Analysis.user_id == owner,
                Analysis.user_paper_id.in_(paper_ids),
                Analysis.status == "completed",
            )
            .order_by(Analysis.user_paper_id, Analysis.language)
        )
    )
    result["paper_summaries"] = []
    for row in summaries:
        snapshot = await analysis_data(db, owner, row)
        result["paper_summaries"].append(
            {
                "user_paper_id": row.user_paper_id,
                "language": row.language,
                "abstract_summary": row.abstract_summary,
                "key_results": row.key_results,
                "is_stale": snapshot["is_stale"],
            }
        )
    result["conversation_summaries"] = []
    for conversation in await conversations(db, owner, project.id):
        latest = await db.scalar(
            select(Message.content)
            .where(
                Message.user_id == owner,
                Message.conversation_id == conversation.id,
                Message.role == "assistant",
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(1)
        )
        result["conversation_summaries"].append(
            {
                **fields(conversation, CONVERSATION_FIELDS),
                "summary": latest[:1000] if latest else None,
                "summary_kind": "latest_assistant_excerpt" if latest else "no_messages",
            }
        )
    result["progress_basis"] = "completed_tasks / all_tasks; no tasks = 0%"
    return result
