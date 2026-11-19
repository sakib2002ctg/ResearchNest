from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.ai.router import private_headers
from app.modules.analytics import service
from app.modules.library.dependencies import LibraryDB, Owner

router = APIRouter(
    prefix="/analytics",
    tags=["Private research analytics"],
    dependencies=[Depends(private_headers)],
)
ProjectID = Annotated[int | None, Query(gt=0, le=2147483647)]


@router.get("/overview")
async def overview(owner: Owner, db: LibraryDB, project_id: ProjectID = None):
    return await service.overview(db, owner, project_id)


@router.get("/timeline")
async def timeline(
    owner: Owner,
    db: LibraryDB,
    project_id: ProjectID = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    return await service.timeline(db, owner, project_id, limit)


@router.get("/knowledge-graph")
async def knowledge_graph(owner: Owner, db: LibraryDB, project_id: ProjectID = None):
    return await service.knowledge_graph(db, owner, project_id)
