"""Membership changes and collaborative edits share the same workspace lock."""

from fastapi import HTTPException
from sqlalchemy import delete, select, update

from app.core.time import utc_now
from app.models.audit_log import AuditLog
from app.models.library import Collection
from app.models.teams import TeamMember, TeamNote, TeamSharedCollection, TeamWorkspace
from app.models.user import User
from app.modules.ai.quota import lock_owner
from app.modules.teams import repository as repo


def audit(db, actor, action, workspace_id, **details):
    db.add(
        AuditLog(
            user_id=actor,
            action=f"team.{action}",
            resource_type="team_workspace",
            resource_id=str(workspace_id),
            details=details or None,
        )
    )


async def lock_workspace(db, actor, workspace_id, permission="write"):
    # Serialize on the workspace alone. Locking actor accounts before workspace
    # mutation can deadlock cross-workspace invitations against the other user's
    # foreign-key lock. This UPDATE also provides SQLite's single-writer lock.
    result = await db.execute(
        update(TeamWorkspace)
        .where(TeamWorkspace.id == workspace_id, repo.membership(actor, workspace_id))
        .values(name=TeamWorkspace.name, updated_at=TeamWorkspace.updated_at)
    )
    if result.rowcount != 1:
        raise HTTPException(404, "Team workspace not found.")
    # A concurrent revocation may have committed while the UPDATE waited.
    # Recheck membership and role in a new statement under the workspace lock.
    return await repo.access(db, actor, workspace_id, permission)


async def create_workspace(db, actor, body):
    await lock_owner(db, actor)
    row = TeamWorkspace(owner_id=actor, **body.model_dump())
    db.add(row)
    await db.flush()
    db.add(
        TeamMember(
            workspace_id=row.id,
            user_id=actor,
            role="owner",
            owner_user_id=actor,
            invited_by_id=actor,
        )
    )
    audit(db, actor, "workspace.created", row.id)
    await db.commit()
    await db.refresh(row)
    return await repo.workspace_data(db, actor, row, "owner", detail=True)


async def update_workspace(db, actor, workspace_id, body):
    row, role = await lock_workspace(db, actor, workspace_id)
    values = body.model_dump(exclude_unset=True)
    if "name" in values and values["name"] is None:
        raise HTTPException(422, "name cannot be null.")
    for name, value in values.items():
        setattr(row, name, value)
    row.updated_at = utc_now()
    audit(db, actor, "workspace.updated", workspace_id)
    await db.commit()
    await db.refresh(row)
    return await repo.workspace_data(db, actor, row, role, detail=True)


async def delete_workspace(db, actor, workspace_id):
    row, _ = await lock_workspace(db, actor, workspace_id, "owner")
    audit(db, actor, "workspace.deleted", workspace_id)
    await db.delete(row)
    await db.commit()


async def add_member(db, actor, workspace_id, body):
    workspace, _ = await lock_workspace(db, actor, workspace_id, "owner")
    identifier = body.identifier
    predicate = (
        User.email == identifier.lower()
        if "@" in identifier
        else User.username == identifier
    )
    user_id = await db.scalar(select(User.id).where(predicate))
    if user_id is None:
        raise HTTPException(404, "Account not available for this invitation.")
    existing = await db.scalar(
        select(TeamMember.id).where(
            TeamMember.workspace_id == workspace_id, TeamMember.user_id == user_id
        )
    )
    if existing is not None:
        raise HTTPException(409, "Account is already a member of this workspace.")
    row = TeamMember(
        workspace_id=workspace_id, user_id=user_id, role=body.role, invited_by_id=actor
    )
    db.add(row)
    workspace.updated_at = utc_now()
    audit(
        db, actor, "member.added", workspace_id, member_user_id=user_id, role=body.role
    )
    await db.commit()
    await db.refresh(row)
    return await repo.member_data(db, actor, row)


async def update_member(db, actor, workspace_id, user_id, body):
    workspace, _ = await lock_workspace(db, actor, workspace_id, "owner")
    row = await repo.member(db, actor, workspace_id, user_id)
    if row.user_id == workspace.owner_id or row.role == "owner":
        raise HTTPException(
            409, "Workspace ownership cannot be changed through membership."
        )
    if row.role != body.role:
        old_role = row.role
        row.role = body.role
        # A demoted member may no longer make their private collections available
        # through the workspace. Deleting grants makes that revocation durable.
        if body.role == "viewer":
            await db.execute(
                delete(TeamSharedCollection).where(
                    TeamSharedCollection.workspace_id == workspace_id,
                    TeamSharedCollection.shared_by_id == user_id,
                )
            )
        audit(
            db,
            actor,
            "member.role_changed",
            workspace_id,
            member_user_id=user_id,
            old_role=old_role,
            role=body.role,
        )
        workspace.updated_at = utc_now()
    await db.commit()
    await db.refresh(row)
    return await repo.member_data(db, actor, row)


async def remove_member(db, actor, workspace_id, user_id):
    workspace, _ = await lock_workspace(db, actor, workspace_id, "owner")
    row = await repo.member(db, actor, workspace_id, user_id)
    if row.user_id == workspace.owner_id or row.role == "owner":
        raise HTTPException(409, "The owner cannot be removed from the workspace.")
    audit(db, actor, "member.removed", workspace_id, member_user_id=user_id)
    await db.delete(row)  # Composite FK cascades revoke this member's shares.
    workspace.updated_at = utc_now()
    await db.commit()


async def share_collection(db, actor, workspace_id, body):
    workspace, _ = await lock_workspace(db, actor, workspace_id)
    collection = await db.scalar(
        select(Collection)
        .where(Collection.id == body.collection_id, Collection.user_id == actor)
        .with_for_update()
    )
    if collection is None:
        raise HTTPException(404, "Collection not found.")
    row = await db.scalar(
        select(TeamSharedCollection).where(
            TeamSharedCollection.workspace_id == workspace_id,
            TeamSharedCollection.collection_id == collection.id,
            TeamSharedCollection.shared_by_id == actor,
        )
    )
    if row is None:
        row = TeamSharedCollection(
            workspace_id=workspace_id, collection_id=collection.id, shared_by_id=actor
        )
        db.add(row)
        audit(db, actor, "collection.shared", workspace_id, collection_id=collection.id)
        workspace.updated_at = utc_now()
    await db.commit()
    await db.refresh(row)
    return await repo.shared_collection_data(db, actor, workspace_id, (row, collection))


async def unshare_collection(db, actor, workspace_id, collection_id):
    workspace, role = await lock_workspace(db, actor, workspace_id)
    row = await db.scalar(
        select(TeamSharedCollection).where(
            TeamSharedCollection.workspace_id == workspace_id,
            TeamSharedCollection.collection_id == collection_id,
            repo.membership(actor, workspace_id),
        )
    )
    if row is None:
        raise HTTPException(404, "Shared collection not found.")
    if (
        not (role == "owner" and workspace.owner_id == actor)
        and row.shared_by_id != actor
    ):
        raise HTTPException(403, "You may only unshare your own collections.")
    audit(db, actor, "collection.unshared", workspace_id, collection_id=collection_id)
    await db.delete(row)
    workspace.updated_at = utc_now()
    await db.commit()


async def create_note(db, actor, workspace_id, body):
    workspace, _ = await lock_workspace(db, actor, workspace_id)
    await repo.validate_paper(db, actor, workspace_id, body.user_paper_id)
    row = TeamNote(workspace_id=workspace_id, author_id=actor, **body.model_dump())
    db.add(row)
    workspace.updated_at = utc_now()
    audit(db, actor, "note.created", workspace_id)
    await db.commit()
    await db.refresh(row)
    return await repo.note_data(db, actor, workspace_id, row)


async def update_note(db, actor, workspace_id, note_id, body):
    workspace, _ = await lock_workspace(db, actor, workspace_id)
    row = await repo.note(db, actor, workspace_id, note_id)
    values = body.model_dump(exclude_unset=True)
    for field in ("title", "content"):
        if field in values and values[field] is None:
            raise HTTPException(422, f"{field} cannot be null.")
    if "user_paper_id" in values and values["user_paper_id"] is not None:
        await repo.validate_paper(db, actor, workspace_id, values["user_paper_id"])
    for field, value in values.items():
        setattr(row, field, value)
    row.updated_at = utc_now()
    workspace.updated_at = utc_now()
    audit(db, actor, "note.updated", workspace_id, note_id=note_id)
    await db.commit()
    await db.refresh(row)
    return await repo.note_data(db, actor, workspace_id, row)


async def delete_note(db, actor, workspace_id, note_id):
    workspace, _ = await lock_workspace(db, actor, workspace_id)
    row = await repo.note(db, actor, workspace_id, note_id)
    audit(db, actor, "note.deleted", workspace_id, note_id=note_id)
    await db.delete(row)
    workspace.updated_at = utc_now()
    await db.commit()
