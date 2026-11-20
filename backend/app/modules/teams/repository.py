"""Workspace membership and live sharing predicates precede private projections."""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import aliased

from app.models.library import Collection, CollectionPaper
from app.models.paper import Paper, UserPaper
from app.models.research_paper import ResearchPaper
from app.models.teams import TeamMember, TeamNote, TeamSharedCollection, TeamWorkspace
from app.models.user import User

DETAIL_MEMBER_LIMIT = 200
DETAIL_COLLECTION_LIMIT = 100
DETAIL_NOTE_LIMIT = 100
COLLECTION_PAPER_LIMIT = 200


def membership(actor, workspace_id):
    member = aliased(TeamMember)
    return exists(
        select(member.id).where(
            member.user_id == actor, member.workspace_id == workspace_id
        )
    )


def value(item):
    if isinstance(item, datetime):
        return item.replace(tzinfo=UTC) if item.tzinfo is None else item.astimezone(UTC)
    return item


def fields(row, names):
    return {key: value(getattr(row, key)) for key in names}


async def access(db, actor, workspace_id, permission="read"):
    row = (
        await db.execute(
            select(TeamWorkspace, TeamMember.role)
            .join(
                TeamMember,
                and_(
                    TeamMember.workspace_id == TeamWorkspace.id,
                    TeamMember.user_id == actor,
                ),
            )
            .where(TeamWorkspace.id == workspace_id)
        )
    ).first()
    if row is None:
        raise HTTPException(404, "Team workspace not found.")
    workspace, role = row
    is_owner = role == "owner" and workspace.owner_id == actor
    if permission == "owner" and not is_owner:
        raise HTTPException(403, "Only the workspace owner can perform this action.")
    if permission == "write" and not (is_owner or role == "editor"):
        raise HTTPException(403, "This workspace is read-only for your role.")
    return workspace, role


async def member(db, actor, workspace_id, user_id):
    row = await db.scalar(
        select(TeamMember).where(
            TeamMember.workspace_id == workspace_id,
            TeamMember.user_id == user_id,
            membership(actor, workspace_id),
        )
    )
    if row is None:
        raise HTTPException(404, "Team member not found.")
    return row


async def member_data(db, actor, row):
    username = await db.scalar(
        select(User.username).where(
            User.id == row.user_id, membership(actor, row.workspace_id)
        )
    )
    return {
        **fields(row, ("user_id", "role", "invited_by_id", "joined_at")),
        "username": username,
    }


def shared_query(actor, workspace_id):
    sharer = aliased(TeamMember)
    return (
        select(TeamSharedCollection, Collection)
        .join(
            Collection,
            and_(
                Collection.id == TeamSharedCollection.collection_id,
                Collection.user_id == TeamSharedCollection.shared_by_id,
            ),
        )
        .join(
            sharer,
            and_(
                sharer.workspace_id == TeamSharedCollection.workspace_id,
                sharer.user_id == TeamSharedCollection.shared_by_id,
                sharer.role.in_(["owner", "editor"]),
            ),
        )
        .where(
            TeamSharedCollection.workspace_id == workspace_id,
            membership(actor, workspace_id),
        )
    )


def shared_papers_query(actor, workspace_id):
    sharer = aliased(TeamMember)
    return (
        select(UserPaper, ResearchPaper, Paper)
        .join(
            CollectionPaper,
            and_(
                CollectionPaper.user_paper_id == UserPaper.id,
                CollectionPaper.user_id == UserPaper.user_id,
            ),
        )
        .join(
            TeamSharedCollection,
            and_(
                TeamSharedCollection.collection_id == CollectionPaper.collection_id,
                TeamSharedCollection.shared_by_id == CollectionPaper.user_id,
                TeamSharedCollection.workspace_id == workspace_id,
            ),
        )
        .join(
            Collection,
            and_(
                Collection.id == CollectionPaper.collection_id,
                Collection.user_id == CollectionPaper.user_id,
            ),
        )
        .join(
            sharer,
            and_(
                sharer.workspace_id == workspace_id,
                sharer.user_id == TeamSharedCollection.shared_by_id,
                sharer.role.in_(["owner", "editor"]),
            ),
        )
        .join(
            ResearchPaper,
            and_(
                ResearchPaper.id == UserPaper.legacy_paper_id,
                ResearchPaper.owner_id == UserPaper.user_id,
            ),
        )
        .outerjoin(Paper, Paper.id == UserPaper.paper_id)
        .where(membership(actor, workspace_id))
    )


async def shared_collection_data(db, actor, workspace_id, row):
    link, collection = row
    query = shared_papers_query(actor, workspace_id).where(
        CollectionPaper.collection_id == collection.id,
        UserPaper.user_id == link.shared_by_id,
    )
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    papers = (
        await db.execute(query.order_by(UserPaper.id).limit(COLLECTION_PAPER_LIMIT))
    ).all()
    return {
        **fields(link, ("id", "collection_id", "shared_by_id", "shared_at")),
        "name": collection.name,
        "description": collection.description,
        "papers": [
            {
                "user_paper_id": saved.id,
                "title": legacy.title,
                "authors": legacy.authors,
                "source": legacy.source,
                "url": legacy.url,
                "doi": canonical.doi if canonical else None,
            }
            for saved, legacy, canonical in papers
        ],
        "total_papers": total or 0,
        "papers_truncated": (total or 0) > len(papers),
    }


async def validate_paper(db, actor, workspace_id, paper_id):
    if paper_id is None:
        return
    paper = await db.scalar(
        shared_papers_query(actor, workspace_id).where(UserPaper.id == paper_id)
    )
    if paper is None:
        raise HTTPException(404, "Shared paper not found.")


async def notes(db, actor, workspace_id, limit=100, offset=0):
    return (
        await db.execute(
            select(TeamNote, User.username)
            .join(User, User.id == TeamNote.author_id)
            .where(
                TeamNote.workspace_id == workspace_id, membership(actor, workspace_id)
            )
            .order_by(TeamNote.updated_at.desc(), TeamNote.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()


async def note_data(db, actor, workspace_id, row, username=None):
    if username is None:
        username = await db.scalar(
            select(User.username).where(
                User.id == row.author_id, membership(actor, workspace_id)
            )
        )
    # A removed share/member must not leave private library identifiers visible.
    paper_id = None
    if row.user_paper_id is not None:
        visible = await db.scalar(
            shared_papers_query(actor, workspace_id).where(
                UserPaper.id == row.user_paper_id
            )
        )
        if visible is not None:
            paper_id = row.user_paper_id
    return {
        **fields(
            row,
            (
                "id",
                "workspace_id",
                "author_id",
                "title",
                "content",
                "created_at",
                "updated_at",
            ),
        ),
        "author_username": username,
        "user_paper_id": paper_id,
    }


async def note(db, actor, workspace_id, note_id):
    row = await db.scalar(
        select(TeamNote).where(
            TeamNote.id == note_id,
            TeamNote.workspace_id == workspace_id,
            membership(actor, workspace_id),
        )
    )
    if row is None:
        raise HTTPException(404, "Team note not found.")
    return row


async def workspace_data(db, actor, row, role, detail=False):
    result = {
        **fields(
            row, ("id", "owner_id", "name", "description", "created_at", "updated_at")
        ),
        "my_role": role,
    }
    for label, model in (
        ("member", TeamMember),
        ("shared_collection", TeamSharedCollection),
        ("note", TeamNote),
    ):
        result[f"{label}_count"] = await db.scalar(
            select(func.count(model.id)).where(
                model.workspace_id == row.id, membership(actor, row.id)
            )
        )
    if detail:
        members = list(
            await db.scalars(
                select(TeamMember)
                .where(TeamMember.workspace_id == row.id, membership(actor, row.id))
                .order_by(TeamMember.id)
                .limit(DETAIL_MEMBER_LIMIT)
            )
        )
        collections = (
            await db.execute(
                shared_query(actor, row.id)
                .order_by(TeamSharedCollection.id)
                .limit(DETAIL_COLLECTION_LIMIT)
            )
        ).all()
        note_rows = await notes(db, actor, row.id, DETAIL_NOTE_LIMIT)
        result.update(
            members=[await member_data(db, actor, item) for item in members],
            collections=[
                await shared_collection_data(db, actor, row.id, item)
                for item in collections
            ],
            notes=[
                await note_data(db, actor, row.id, item, username)
                for item, username in note_rows
            ],
            members_truncated=result["member_count"] > len(members),
            collections_truncated=result["shared_collection_count"] > len(collections),
            notes_truncated=result["note_count"] > len(note_rows),
        )
    return result


async def list_workspaces(db, actor, limit, offset):
    rows = (
        await db.execute(
            select(TeamWorkspace, TeamMember.role)
            .join(
                TeamMember,
                and_(
                    TeamMember.workspace_id == TeamWorkspace.id,
                    TeamMember.user_id == actor,
                ),
            )
            .order_by(TeamWorkspace.updated_at.desc(), TeamWorkspace.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [await workspace_data(db, actor, row, role) for row, role in rows]
