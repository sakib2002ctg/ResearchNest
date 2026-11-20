"""Project orchestration; owner locks serialize edits and derived progress."""

from fastapi import HTTPException
from sqlalchemy import select

from app.core.time import utc_now
from app.models.assistant import Conversation
from app.models.projects import ProjectPaper, ProjectTask, ResearchNote, ResearchProject
from app.modules.ai.quota import lock_owner
from app.modules.projects import repository as repo


def touch(project):
    project.revision += 1
    project.updated_at = utc_now()


def changes(body, required=()):
    values = body.model_dump(exclude_unset=True)
    for key in required:
        if key in values and values[key] is None:
            raise HTTPException(422, f"{key} cannot be null.")
    return values


async def create_project(db, owner, body):
    await lock_owner(db, owner)
    await repo.validate_collection(db, owner, body.collection_id)
    row = ResearchProject(user_id=owner, **body.model_dump())
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return await repo.project_data(db, owner, row, detail=True)


async def update_project(db, owner, project_id, body):
    await lock_owner(db, owner)
    row = await repo.owned_project(db, owner, project_id)
    values = changes(body, ("title", "objectives", "status"))
    expected = values.pop("expected_revision", None)
    if expected is not None and expected != row.revision:
        raise HTTPException(409, "Project changed. Reload it before saving.")
    if "collection_id" in values:
        await repo.validate_collection(db, owner, values["collection_id"])
    for name, value in values.items():
        setattr(row, name, value)
    if values:
        touch(row)
    await db.commit()
    await db.refresh(row)
    return await repo.project_data(db, owner, row, detail=True)


async def delete_project(db, owner, project_id):
    await lock_owner(db, owner)
    row = await repo.owned_project(db, owner, project_id)
    await db.delete(row)
    await db.commit()


async def add_paper(db, owner, project_id, body):
    await lock_owner(db, owner)
    project = await repo.owned_project(db, owner, project_id)
    await repo.validate_paper(db, owner, body.user_paper_id)
    row = await db.scalar(
        select(ProjectPaper).where(
            ProjectPaper.user_id == owner,
            ProjectPaper.project_id == project_id,
            ProjectPaper.user_paper_id == body.user_paper_id,
        )
    )
    if row is None:
        row = ProjectPaper(user_id=owner, project_id=project_id, **body.model_dump())
        db.add(row)
    else:
        row.role_in_project = body.role_in_project
    touch(project)
    await db.commit()
    return next(
        repo.paper_data(item)
        for item in await repo.papers(db, owner, project_id)
        if item[0].user_paper_id == body.user_paper_id
    )


async def remove_paper(db, owner, project_id, paper_id):
    await lock_owner(db, owner)
    project = await repo.owned_project(db, owner, project_id)
    row = await db.scalar(
        select(ProjectPaper).where(
            ProjectPaper.user_id == owner,
            ProjectPaper.project_id == project_id,
            ProjectPaper.user_paper_id == paper_id,
        )
    )
    if row is None:
        raise HTTPException(404, "Project paper not found.")
    await db.delete(row)
    touch(project)
    await db.commit()


async def create_note(db, owner, project_id, body):
    await lock_owner(db, owner)
    project = await repo.owned_project(db, owner, project_id)
    await repo.validate_paper(db, owner, body.user_paper_id)
    row = ResearchNote(user_id=owner, project_id=project_id, **body.model_dump())
    db.add(row)
    touch(project)
    await db.commit()
    await db.refresh(row)
    return repo.fields(row, repo.NOTE_FIELDS)


async def update_note(db, owner, project_id, note_id, body):
    await lock_owner(db, owner)
    project = await repo.owned_project(db, owner, project_id)
    row = await repo.owned_resource(db, owner, ResearchNote, note_id, project_id)
    values = changes(body, ("title", "content"))
    if "user_paper_id" in values:
        await repo.validate_paper(db, owner, values["user_paper_id"])
    for name, value in values.items():
        setattr(row, name, value)
    row.updated_at = utc_now()
    touch(project)
    await db.commit()
    await db.refresh(row)
    return repo.fields(row, repo.NOTE_FIELDS)


async def delete_note(db, owner, project_id, note_id):
    await lock_owner(db, owner)
    project = await repo.owned_project(db, owner, project_id)
    row = await repo.owned_resource(db, owner, ResearchNote, note_id, project_id)
    await db.delete(row)
    touch(project)
    await db.commit()


async def create_task(db, owner, project_id, body):
    await lock_owner(db, owner)
    project = await repo.owned_project(db, owner, project_id)
    row = ProjectTask(
        user_id=owner,
        project_id=project_id,
        completed_at=utc_now() if body.status == "done" else None,
        **body.model_dump(),
    )
    db.add(row)
    await repo.recompute_progress(db, owner, project)
    touch(project)
    await db.commit()
    await db.refresh(row)
    return repo.fields(row, repo.TASK_FIELDS)


async def update_task(db, owner, project_id, task_id, body):
    await lock_owner(db, owner)
    project = await repo.owned_project(db, owner, project_id)
    row = await repo.owned_resource(db, owner, ProjectTask, task_id, project_id)
    values = changes(body, ("title", "status", "is_milestone"))
    for name, value in values.items():
        setattr(row, name, value)
    if "status" in values:
        row.completed_at = (
            (row.completed_at or utc_now()) if row.status == "done" else None
        )
    row.updated_at = utc_now()
    await repo.recompute_progress(db, owner, project)
    touch(project)
    await db.commit()
    await db.refresh(row)
    return repo.fields(row, repo.TASK_FIELDS)


async def delete_task(db, owner, project_id, task_id):
    await lock_owner(db, owner)
    project = await repo.owned_project(db, owner, project_id)
    row = await repo.owned_resource(db, owner, ProjectTask, task_id, project_id)
    await db.delete(row)
    await repo.recompute_progress(db, owner, project)
    touch(project)
    await db.commit()


async def link_conversation(db, owner, project_id, conversation_id):
    await lock_owner(db, owner)
    project = await repo.owned_project(db, owner, project_id)
    row = await repo.owned_resource(db, owner, Conversation, conversation_id)
    row.project_id = project_id
    touch(project)
    await db.commit()
    await db.refresh(row)
    return repo.fields(row, repo.CONVERSATION_FIELDS)


def markdown(bundle):
    """Plain Markdown export; no generated interpretations or provider calls."""

    def timestamp(value):
        return value.isoformat() if value else "Not set"

    lines = [
        f"# {bundle['title']}",
        "",
        bundle["description"] or "",
        "",
        f"Status: {bundle['status']}",
        f"Progress: {bundle['progress_percent']:g}%",
        f"Target deadline: {timestamp(bundle['target_deadline'])}",
        "",
        "## Objectives",
        "",
    ]
    lines += [f"- {item}" for item in bundle["objectives"]] or ["None recorded."]
    lines += ["", "## Papers", ""]
    for paper in bundle["papers"]:
        lines += [
            f"- {paper['title']}"
            + (f" — {paper['role_in_project']}" if paper["role_in_project"] else "")
        ]
        lines += [
            f"  Authors: {paper['authors'] or 'Not recorded'}",
            f"  DOI: {paper['doi'] or 'Not recorded'}",
            f"  URL: {paper['url'] or 'Not recorded'}",
            f"  Reading status: {paper['reading_status']}",
        ]
    lines += ["", "## Tasks and milestones", ""]
    for task in bundle["tasks"]:
        lines += [
            f"- [{'x' if task['status'] == 'done' else ' '}] {task['title']}"
            + (" (milestone)" if task["is_milestone"] else "")
            + f" — {task['status']}"
        ]
        if task["description"]:
            lines += [task["description"]]
        lines += [
            f"  Due: {timestamp(task['due_date'])}",
            f"  Completed: {timestamp(task['completed_at'])}",
        ]
    lines += ["", "## Research notes", ""]
    for note in bundle["notes"]:
        lines += [f"### {note['title']}", "", note["content"], ""]
    lines += ["", "## Paper summaries", ""]
    for summary in bundle["paper_summaries"]:
        lines += [
            f"### Library paper {summary['user_paper_id']} ({summary['language']})",
            "",
            summary["abstract_summary"],
            "",
            summary["key_results"],
            "",
        ]
        if summary["is_stale"]:
            lines += ["Warning: this summary is stale after source changes.", ""]
    lines += ["", "## Conversation summaries", ""]
    for conversation in bundle["conversation_summaries"]:
        lines += [
            f"### {conversation['title']}",
            "",
            "Latest assistant excerpt:",
            "",
            conversation["summary"] or "No assistant messages.",
            "",
        ]
    lines += ["", "## Bibliography", ""] + bundle["bibliography"]["bibliography"]
    if bundle["bibliography"]["warnings"]:
        lines += ["", "### Metadata warnings", ""]
        lines += [f"- {item}" for item in bundle["bibliography"]["warnings"]]
    return "\n".join(lines).strip() + "\n"
