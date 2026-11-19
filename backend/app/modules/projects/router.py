from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response

from app.modules.ai.router import private_headers
from app.modules.ai.schemas import ID
from app.modules.library.dependencies import LibraryDB, Owner
from app.modules.projects import repository as repo
from app.modules.projects import service
from app.modules.projects.schemas import (
    AddPaper,
    CreateNote,
    CreateProject,
    CreateTask,
    ProjectStatus,
    UpdateNote,
    UpdateProject,
    UpdateTask,
)

router = APIRouter(
    prefix="/projects",
    tags=["Research projects"],
    dependencies=[Depends(private_headers)],
)


@router.get("")
async def list_projects(
    owner: Owner,
    db: LibraryDB,
    status: ProjectStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
):
    return await repo.list_projects(db, owner, status, limit, offset)


@router.post("", status_code=201)
async def create_project(body: CreateProject, owner: Owner, db: LibraryDB):
    return await service.create_project(db, owner, body)


@router.get("/{project_id}")
async def get_project(project_id: ID, owner: Owner, db: LibraryDB):
    row = await repo.owned_project(db, owner, project_id)
    return await repo.project_data(db, owner, row, detail=True)


@router.put("/{project_id}")
async def update_project(
    project_id: ID, body: UpdateProject, owner: Owner, db: LibraryDB
):
    return await service.update_project(db, owner, project_id, body)


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: ID, owner: Owner, db: LibraryDB):
    await service.delete_project(db, owner, project_id)
    return None


@router.post("/{project_id}/papers", status_code=201)
async def add_paper(project_id: ID, body: AddPaper, owner: Owner, db: LibraryDB):
    return await service.add_paper(db, owner, project_id, body)


@router.delete("/{project_id}/papers/{user_paper_id}", status_code=204)
async def remove_paper(project_id: ID, user_paper_id: ID, owner: Owner, db: LibraryDB):
    await service.remove_paper(db, owner, project_id, user_paper_id)
    return None


@router.get("/{project_id}/notes")
async def list_notes(project_id: ID, owner: Owner, db: LibraryDB):
    await repo.owned_project(db, owner, project_id)
    return [
        repo.fields(row, repo.NOTE_FIELDS)
        for row in await repo.notes(db, owner, project_id)
    ]


@router.post("/{project_id}/notes", status_code=201)
async def create_note(project_id: ID, body: CreateNote, owner: Owner, db: LibraryDB):
    return await service.create_note(db, owner, project_id, body)


@router.put("/{project_id}/notes/{note_id}")
async def update_note(
    project_id: ID,
    note_id: ID,
    body: UpdateNote,
    owner: Owner,
    db: LibraryDB,
):
    return await service.update_note(db, owner, project_id, note_id, body)


@router.delete("/{project_id}/notes/{note_id}", status_code=204)
async def delete_note(project_id: ID, note_id: ID, owner: Owner, db: LibraryDB):
    await service.delete_note(db, owner, project_id, note_id)
    return None


@router.get("/{project_id}/tasks")
async def list_tasks(project_id: ID, owner: Owner, db: LibraryDB):
    await repo.owned_project(db, owner, project_id)
    return [
        repo.fields(row, repo.TASK_FIELDS)
        for row in await repo.tasks(db, owner, project_id)
    ]


@router.post("/{project_id}/tasks", status_code=201)
async def create_task(project_id: ID, body: CreateTask, owner: Owner, db: LibraryDB):
    return await service.create_task(db, owner, project_id, body)


@router.put("/{project_id}/tasks/{task_id}")
async def update_task(
    project_id: ID,
    task_id: ID,
    body: UpdateTask,
    owner: Owner,
    db: LibraryDB,
):
    return await service.update_task(db, owner, project_id, task_id, body)


@router.delete("/{project_id}/tasks/{task_id}", status_code=204)
async def delete_task(project_id: ID, task_id: ID, owner: Owner, db: LibraryDB):
    await service.delete_task(db, owner, project_id, task_id)
    return None


@router.post("/{project_id}/conversations/{conversation_id}")
async def link_conversation(
    project_id: ID,
    conversation_id: ID,
    owner: Owner,
    db: LibraryDB,
):
    return await service.link_conversation(db, owner, project_id, conversation_id)


@router.get("/{project_id}/export")
async def export_project(
    project_id: ID,
    owner: Owner,
    db: LibraryDB,
    format: Literal["json", "markdown"] = "json",
    citation_style: Literal["apa", "ieee", "mla", "chicago", "harvard"] = "apa",
):
    project = await repo.owned_project(db, owner, project_id)
    bundle = await repo.export_data(db, owner, project, citation_style)
    if format == "markdown":
        return Response(
            service.markdown(bundle),
            media_type="text/markdown",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="project-{project_id}.md"'
                ),
                "Cache-Control": "private, no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )
    return bundle
