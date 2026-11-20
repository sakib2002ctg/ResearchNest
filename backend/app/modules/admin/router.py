from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.modules.admin import repository as repo
from app.modules.admin import service
from app.modules.admin.dependencies import Admin
from app.modules.ai.router import private_headers
from app.modules.ai.schemas import ID
from app.modules.library.dependencies import LibraryDB

router = APIRouter(
    prefix="/admin",
    tags=["Operational administration"],
    dependencies=[Depends(private_headers)],
)
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0, le=10000)]


@router.get("/overview")
async def overview(actor: Admin, db: LibraryDB):
    return await service.read(
        db, actor, "overview.read", lambda: repo.overview(db, actor)
    )


@router.get("/users")
async def users(actor: Admin, db: LibraryDB, limit: Limit = 30, offset: Offset = 0):
    return await service.read(
        db,
        actor,
        "users.listed",
        lambda: repo.users(db, actor, limit, offset),
        limit=limit,
        offset=offset,
    )


@router.post("/users/{user_id}/revoke-sessions")
async def revoke_sessions(user_id: ID, actor: Admin, db: LibraryDB):
    return await service.revoke_sessions(db, actor, user_id)


@router.get("/audit-logs")
async def audit_logs(
    actor: Admin,
    db: LibraryDB,
    limit: Limit = 30,
    offset: Offset = 0,
    action: Annotated[
        str | None, Query(min_length=1, max_length=100, pattern=r"^[a-z0-9._-]+$")
    ] = None,
    user_id: Annotated[int | None, Query(ge=1, le=2147483647)] = None,
):
    return await service.read(
        db,
        actor,
        "audit_logs.viewed",
        lambda: repo.audit_logs(db, actor, limit, offset, action, user_id),
        limit=limit,
        offset=offset,
        action_filter=action is not None,
        target_user_id=user_id,
    )


@router.get("/jobs/failed")
async def failed_jobs(
    actor: Admin, db: LibraryDB, limit: Limit = 30, offset: Offset = 0
):
    return await service.read(
        db,
        actor,
        "failed_jobs.listed",
        lambda: repo.failed_jobs(db, actor, limit, offset),
        limit=limit,
        offset=offset,
    )


@router.post("/jobs/{job_id}/requeue")
async def requeue(job_id: ID, actor: Admin, db: LibraryDB, request: Request):
    return await service.requeue(
        db, actor, job_id, request.app.state.document_dispatcher
    )
