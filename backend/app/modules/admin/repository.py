"""Safe operational projections guarded by a live administrative capability."""

import re
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import aliased

from app.core.time import utc_now
from app.models.assistant import AIUsage
from app.models.audit_log import AuditLog
from app.models.document_intelligence import DocumentChunk, Embedding, ProcessingJob
from app.models.library import Document
from app.models.paper import Paper, UserPaper
from app.models.research_paper import ResearchPaper
from app.models.session import Session
from app.models.teams import TeamWorkspace
from app.models.user import User


def capability(actor):
    administrator = aliased(User)
    session = aliased(Session)
    return exists(
        select(administrator.id)
        .join(session, session.user_id == administrator.id)
        .where(
            administrator.id == actor.user_id,
            administrator.is_admin.is_(True),
            session.id == actor.session_id,
            session.token_jti == actor.token_jti,
            session.is_revoked.is_(False),
            session.revoked_at.is_(None),
            session.expires_at > utc_now(),
        )
    )


async def require_capability(db, actor):
    if not await db.scalar(select(capability(actor))):
        active = await db.scalar(
            select(Session.id).where(
                Session.user_id == actor.user_id,
                Session.id == actor.session_id,
                Session.token_jti == actor.token_jti,
                Session.is_revoked.is_(False),
                Session.revoked_at.is_(None),
                Session.expires_at > utc_now(),
            )
        )
        if active is None:
            raise HTTPException(
                401,
                "Could not validate credentials.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        raise HTTPException(403, "Administrative access required.")


def active_sessions():
    return (
        Session.is_revoked.is_(False),
        Session.revoked_at.is_(None),
        Session.expires_at > utc_now(),
    )


def count(model, *conditions):
    return select(func.count(model.id)).where(*conditions).scalar_subquery()


def utc(value):
    if isinstance(value, datetime) and value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


def pagination(items, total, limit, offset):
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(items) < total,
    }


async def overview(db, actor):
    current_index = exists(
        select(DocumentChunk.id)
        .join(
            Embedding,
            and_(
                Embedding.chunk_id == DocumentChunk.id,
                Embedding.user_id == Document.user_id,
                Embedding.document_version == Document.version,
            ),
        )
        .where(
            DocumentChunk.document_id == Document.id,
            DocumentChunk.user_id == Document.user_id,
            DocumentChunk.document_version == Document.version,
        )
    )
    counts = (
        (
            await db.execute(
                select(
                    count(User).label("total_users"),
                    count(User, User.is_verified.is_(True)).label("verified_users"),
                    count(Session, *active_sessions()).label("active_sessions"),
                    count(Paper).label("total_papers"),
                    count(UserPaper).label("total_library_papers"),
                    count(ResearchPaper).label("legacy_paper_records"),
                    count(
                        Document, Document.status == "completed", current_index
                    ).label("indexed_documents"),
                    count(ProcessingJob, ProcessingJob.status == "failed").label(
                        "failed_processing_jobs"
                    ),
                    count(TeamWorkspace).label("active_team_workspaces"),
                ).where(capability(actor))
            )
        )
        .mappings()
        .first()
    )
    if counts is None:
        await require_capability(db, actor)
        raise HTTPException(403, "Administrative access required.")
    usages = (
        await db.execute(
            select(
                AIUsage.status,
                func.count(AIUsage.id),
                func.coalesce(func.sum(AIUsage.prompt_tokens), 0),
                func.coalesce(func.sum(AIUsage.completion_tokens), 0),
                func.coalesce(func.sum(AIUsage.reserved_tokens), 0),
            )
            .where(capability(actor))
            .group_by(AIUsage.status)
        )
    ).all()
    return {
        "status": "ok",
        "version": "2.0.0",
        "counts": dict(counts),
        "health": {"database": "ok", "readiness_endpoint": "/health/ready"},
        "ai_usage": {
            "requests": sum(row[1] for row in usages),
            "prompt_tokens": sum(row[2] for row in usages),
            "completion_tokens": sum(row[3] for row in usages),
            "reserved_unsettled_tokens": sum(
                row[4] for row in usages if row[0] != "completed"
            ),
            "status_counts": {row[0]: row[1] for row in usages},
        },
    }


async def users(db, actor, limit, offset):
    total = await db.scalar(select(func.count(User.id)).where(capability(actor))) or 0
    statement = (
        select(
            User.id,
            User.username,
            User.email,
            User.is_verified,
            User.is_admin,
            select(func.count(Session.id))
            .where(Session.user_id == User.id, *active_sessions())
            .correlate(User)
            .scalar_subquery()
            .label("active_sessions"),
            select(func.count(UserPaper.id))
            .where(UserPaper.user_id == User.id)
            .correlate(User)
            .scalar_subquery()
            .label("saved_papers"),
            select(func.count(AuditLog.id))
            .where(AuditLog.user_id == User.id)
            .correlate(User)
            .scalar_subquery()
            .label("activity_events"),
            select(func.max(AuditLog.created_at))
            .where(AuditLog.user_id == User.id)
            .correlate(User)
            .scalar_subquery()
            .label("last_activity_at"),
        )
        .where(capability(actor))
        .order_by(User.id)
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(statement)).mappings().all()
    return pagination(
        [{key: utc(value) for key, value in row.items()} for row in rows],
        total,
        limit,
        offset,
    )


def safe_resource_id(value):
    if value is not None and re.fullmatch(r"(?:[0-9]{1,10}|[0-9a-fA-F-]{36})", value):
        return value
    return None


async def audit_logs(db, actor, limit, offset, action, user_id):
    conditions = [capability(actor)]
    if action is not None:
        conditions.append(AuditLog.action == action)
    if user_id is not None:
        conditions.append(AuditLog.user_id == user_id)
    total = await db.scalar(select(func.count(AuditLog.id)).where(*conditions)) or 0
    rows = list(
        await db.scalars(
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    # Details and IP context are deliberately excluded: older producers may have
    # stored unstructured values. Operators see event attribution and safe IDs.
    items = [
        {
            "id": row.id,
            "user_id": row.user_id,
            "action": (
                row.action
                if re.fullmatch(r"[a-z0-9._-]{1,100}", row.action)
                else "unrecognized"
            ),
            "resource_type": (
                row.resource_type
                if row.resource_type
                and re.fullmatch(r"[a-z_]{1,50}", row.resource_type)
                else None
            ),
            "resource_id": safe_resource_id(row.resource_id),
            "created_at": utc(row.created_at),
        }
        for row in rows
    ]
    return pagination(items, total, limit, offset)


def failed_job_data(job, document):
    current = job.document_version == document.version
    return {
        "id": job.id,
        "user_id": job.user_id,
        "document_id": job.document_id,
        "document_version": job.document_version,
        "current_document_version": document.version,
        "job_type": job.job_type,
        "status": job.status,
        "attempts": job.attempts,
        "created_at": utc(job.created_at),
        "started_at": utc(job.started_at),
        "completed_at": utc(job.completed_at),
        "is_current": current,
        "can_requeue": current
        and job.status == "failed"
        and document.status == "failed",
    }


async def failed_jobs(db, actor, limit, offset):
    query = (
        select(ProcessingJob, Document)
        .join(
            Document,
            and_(
                Document.id == ProcessingJob.document_id,
                Document.user_id == ProcessingJob.user_id,
            ),
        )
        .where(ProcessingJob.status == "failed", capability(actor))
    )
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        await db.execute(
            query.order_by(ProcessingJob.created_at.desc(), ProcessingJob.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return pagination(
        [failed_job_data(job, document) for job, document in rows], total, limit, offset
    )
