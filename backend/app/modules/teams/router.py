from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.ai.router import private_headers
from app.modules.ai.schemas import ID
from app.modules.library.dependencies import LibraryDB, Owner
from app.modules.teams import repository as repo
from app.modules.teams import service
from app.modules.teams.schemas import (
    AddMember,
    CreateNote,
    CreateWorkspace,
    ShareCollection,
    UpdateMember,
    UpdateNote,
    UpdateWorkspace,
)

router = APIRouter(
    prefix="/teams",
    tags=["Team collaboration"],
    dependencies=[Depends(private_headers)],
)


@router.get("")
async def list_workspaces(
    owner: Owner,
    db: LibraryDB,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
):
    return await repo.list_workspaces(db, owner, limit, offset)


@router.post("", status_code=201)
async def create_workspace(body: CreateWorkspace, owner: Owner, db: LibraryDB):
    return await service.create_workspace(db, owner, body)


@router.get("/{workspace_id}")
async def get_workspace(workspace_id: ID, owner: Owner, db: LibraryDB):
    row, role = await repo.access(db, owner, workspace_id)
    return await repo.workspace_data(db, owner, row, role, detail=True)


@router.put("/{workspace_id}")
async def update_workspace(
    workspace_id: ID, body: UpdateWorkspace, owner: Owner, db: LibraryDB
):
    return await service.update_workspace(db, owner, workspace_id, body)


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(workspace_id: ID, owner: Owner, db: LibraryDB):
    await service.delete_workspace(db, owner, workspace_id)


@router.post("/{workspace_id}/members", status_code=201)
async def add_member(workspace_id: ID, body: AddMember, owner: Owner, db: LibraryDB):
    return await service.add_member(db, owner, workspace_id, body)


@router.put("/{workspace_id}/members/{member_user_id}")
async def update_member(
    workspace_id: ID,
    member_user_id: ID,
    body: UpdateMember,
    owner: Owner,
    db: LibraryDB,
):
    return await service.update_member(db, owner, workspace_id, member_user_id, body)


@router.delete("/{workspace_id}/members/{member_user_id}", status_code=204)
async def remove_member(
    workspace_id: ID, member_user_id: ID, owner: Owner, db: LibraryDB
):
    await service.remove_member(db, owner, workspace_id, member_user_id)


@router.post("/{workspace_id}/collections", status_code=201)
async def share_collection(
    workspace_id: ID, body: ShareCollection, owner: Owner, db: LibraryDB
):
    return await service.share_collection(db, owner, workspace_id, body)


@router.delete("/{workspace_id}/collections/{collection_id}", status_code=204)
async def unshare_collection(
    workspace_id: ID, collection_id: ID, owner: Owner, db: LibraryDB
):
    await service.unshare_collection(db, owner, workspace_id, collection_id)


@router.get("/{workspace_id}/notes")
async def list_notes(
    workspace_id: ID,
    owner: Owner,
    db: LibraryDB,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
):
    await repo.access(db, owner, workspace_id)
    return [
        await repo.note_data(db, owner, workspace_id, row, username)
        for row, username in await repo.notes(db, owner, workspace_id, limit, offset)
    ]


@router.post("/{workspace_id}/notes", status_code=201)
async def create_note(workspace_id: ID, body: CreateNote, owner: Owner, db: LibraryDB):
    return await service.create_note(db, owner, workspace_id, body)


@router.put("/{workspace_id}/notes/{note_id}")
async def update_note(
    workspace_id: ID, note_id: ID, body: UpdateNote, owner: Owner, db: LibraryDB
):
    return await service.update_note(db, owner, workspace_id, note_id, body)


@router.delete("/{workspace_id}/notes/{note_id}", status_code=204)
async def delete_note(workspace_id: ID, note_id: ID, owner: Owner, db: LibraryDB):
    await service.delete_note(db, owner, workspace_id, note_id)
