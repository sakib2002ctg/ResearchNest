"""Audited, serialized emergency actions without private document projections."""

from fastapi import HTTPException
from sqlalchemy import and_, select, update

from app.core.logging import logger
from app.core.time import utc_now
from app.models.audit_log import AuditLog
from app.models.document_intelligence import ProcessingJob
from app.models.library import Document
from app.models.session import Session
from app.models.user import User
from app.modules.admin import repository as repo


def audit(db, actor, action, resource_type="admin", resource_id=None, **details):
    db.add(
        AuditLog(
            user_id=actor.user_id,
            action=f"admin.{action}",
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            details=details or None,
        )
    )


async def lock_accounts(db, user_ids):
    for user_id in sorted(set(user_ids)):
        # A non-key column update serializes account decisions on SQLite/Postgres
        # without blocking FK KEY SHARE checks as a username-key update would.
        await db.execute(
            update(User).where(User.id == user_id).values(is_admin=User.is_admin)
        )


async def _read(db, actor, action, operation, **details):
    await repo.require_capability(db, actor)
    payload = await operation()
    audit(db, actor, action, **details)
    await db.commit()
    return payload


async def _revoke_sessions(db, actor, user_id):
    await lock_accounts(db, [actor.user_id, user_id])
    await repo.require_capability(db, actor)
    if await db.scalar(select(User.id).where(User.id == user_id)) is None:
        raise HTTPException(404, "Account not found.")
    now = utc_now()
    result = await db.execute(
        update(Session)
        .where(
            Session.user_id == user_id,
            *repo.active_sessions(),
        )
        .values(is_revoked=True, revoked_at=now)
    )
    count = result.rowcount
    audit(db, actor, "sessions.revoked", "user", user_id, revoked_sessions=count)
    await db.commit()
    return {"user_id": user_id, "revoked_sessions": count}


async def _requeue(db, actor, job_id, dispatcher):
    await repo.require_capability(db, actor)
    locator = (
        await db.execute(
            select(ProcessingJob.document_id, ProcessingJob.user_id).where(
                ProcessingJob.id == job_id, repo.capability(actor)
            )
        )
    ).one_or_none()
    if locator is None:
        raise HTTPException(404, "Processing job not found.")
    document_id, owner = locator
    await db.rollback()
    # Keep processor's document -> job lock order and keep the actor's non-key
    # account lock compatible with the worker's audit FK check.
    await lock_accounts(db, [actor.user_id])
    await repo.require_capability(db, actor)
    document = await db.scalar(
        select(Document)
        .where(
            Document.id == document_id,
            Document.user_id == owner,
        )
        .with_for_update()
    )
    job = await db.scalar(
        select(ProcessingJob)
        .join(
            Document,
            and_(
                Document.id == ProcessingJob.document_id,
                Document.user_id == ProcessingJob.user_id,
            ),
        )
        .where(
            ProcessingJob.id == job_id,
            ProcessingJob.document_id == document_id,
            ProcessingJob.user_id == owner,
        )
        .with_for_update()
    )
    if document is None or job is None:
        raise HTTPException(404, "Processing job not found.")
    if (
        job.status != "failed"
        or document.status != "failed"
        or job.document_version != document.version
    ):
        raise HTTPException(
            409, "Only a failed job for the current failed document can be requeued."
        )
    # Attempts are worker fencing tokens. Reusing the same job/version and
    # resetting its counter could let an old leased attempt match a new attempt.
    # Retain that failed history and create an independently fenced generation.
    document.version += 1
    document.status, document.error_message, document.updated_at = (
        "pending",
        None,
        utc_now(),
    )
    replacement = ProcessingJob(
        document_id=document_id,
        user_id=owner,
        document_version=document.version,
        status="queued",
        attempts=0,
    )
    db.add(replacement)
    await db.flush()
    new_job_id = replacement.id
    audit(
        db,
        actor,
        "job.requeued",
        "processing_job",
        job_id,
        document_id=document_id,
        owner_user_id=owner,
        document_version=document.version,
        queued_job_id=new_job_id,
    )
    payload = {
        "id": new_job_id,
        "requested_job_id": job_id,
        "user_id": owner,
        "document_id": document_id,
        "document_version": document.version,
        "status": "queued",
        "attempts": 0,
    }
    await db.commit()
    # The committed queued row is the durable source of truth. Polling recovers
    # it even if broker dispatch fails; never change an acknowledged job back.
    try:
        await dispatcher.enqueue(new_job_id)
    except Exception:
        logger.warning("Admin job dispatch deferred to durable queue recovery.")
    return payload


async def record_outcome(
    db, actor, operation, perform, resource_type="admin", resource_id=None
):
    """Retain denied operational attempts without retaining exception contents."""
    try:
        return await perform()
    except HTTPException as denied:
        # An action may have acquired locks or staged changes before rejecting
        # it. None of that work may be committed with the denial's audit event.
        await db.rollback()
        actor_id = await db.scalar(
            select(User.id)
            .where(User.id == actor.user_id)
            .with_for_update(read=True, key_share=True)
        )
        db.add(
            AuditLog(
                user_id=actor_id,
                action="admin.action.denied",
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                details={"operation": operation, "status": denied.status_code},
            )
        )
        # Audit persistence failures propagate as errors; never acknowledge an
        # action whose required security record could not be persisted.
        await db.commit()
        raise


async def read(db, actor, action, operation, **details):
    return await record_outcome(
        db, actor, action, lambda: _read(db, actor, action, operation, **details)
    )


async def revoke_sessions(db, actor, user_id):
    return await record_outcome(
        db,
        actor,
        "sessions.revoke",
        lambda: _revoke_sessions(db, actor, user_id),
        "user",
        user_id,
    )


async def requeue(db, actor, job_id, dispatcher):
    return await record_outcome(
        db,
        actor,
        "job.requeue",
        lambda: _requeue(db, actor, job_id, dispatcher),
        "processing_job",
        job_id,
    )
