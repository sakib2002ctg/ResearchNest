from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.modules.ai.gateway import AIProviderGateway
from app.modules.ai.router import get_gateway, private_headers
from app.modules.ai.schemas import ID
from app.modules.education import catalog, service
from app.modules.education import repository as repo
from app.modules.education.schemas import ExplainRequest, ProgressUpdate
from app.modules.library.dependencies import LibraryDB, Owner

router = APIRouter(
    prefix="/education",
    tags=["Research education"],
    dependencies=[Depends(private_headers)],
)


@router.get("/guides")
async def list_guides(owner: Owner, db: LibraryDB):
    return await repo.list_guides(db, owner)


@router.get("/guides/{slug}")
async def get_guide(slug: str, owner: Owner, db: LibraryDB):
    guide = repo.require_guide(slug)
    return {
        **guide,
        "progress": repo.progress_data(
            guide, await repo.owned_progress(db, owner, slug)
        ),
    }


@router.post("/guides/{slug}/progress")
async def update_progress(
    slug: str, request: ProgressUpdate, owner: Owner, db: LibraryDB
):
    return await service.update_progress(db, owner, slug, request)


@router.get("/glossary")
async def glossary(
    owner: Owner,
    q: Annotated[str, Query(max_length=200)] = "",
    category: Annotated[str | None, Query(max_length=40)] = None,
):
    return catalog.glossary(q, category)


@router.post("/explain-paper/{user_paper_id}")
async def explain_paper(
    user_paper_id: ID,
    request: ExplainRequest,
    owner: Owner,
    db: LibraryDB,
    gateway: Annotated[AIProviderGateway, Depends(get_gateway)],
):
    return await service.explain(db, owner, user_paper_id, request, gateway)
