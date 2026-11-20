from datetime import UTC

from fastapi import HTTPException
from sqlalchemy import select

from app.models.education import LearningProgress
from app.modules.education import catalog


def require_guide(slug):
    result = catalog.guide(slug)
    if result is None:
        raise HTTPException(404, "Guide not found.")
    return result


def progress_data(guide, row):
    # Ignore obsolete catalog step IDs after a curated curriculum revision.
    valid = [step["id"] for step in guide["steps"]]
    completed = [step for step in valid if row and step in row.completed_step_ids]
    updated = row.updated_at if row else None
    if updated is not None and updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return {
        "completed_step_ids": completed,
        "is_completed": len(completed) == len(valid),
        "updated_at": updated,
        "percent": round(len(completed) * 100 / len(valid), 2) if valid else 0,
    }


async def list_guides(db, owner):
    rows = list(
        await db.scalars(
            select(LearningProgress).where(LearningProgress.user_id == owner)
        )
    )
    progress = {row.guide_slug: row for row in rows}
    return [
        {**guide, "progress": progress_data(guide, progress.get(guide["slug"]))}
        for guide in (catalog.guide(item["slug"]) for item in catalog.GUIDES)
    ]


async def owned_progress(db, owner, slug):
    return await db.scalar(
        select(LearningProgress).where(
            LearningProgress.user_id == owner, LearningProgress.guide_slug == slug
        )
    )
