from fastapi import APIRouter, Depends, Query

from app.dependencies.research_dependencies import (
    get_research_service,
)
from app.schemas.external_paper import (
    ExternalPaperSearchResponse,
)
from app.services.research_service import (
    ResearchService,
)

router = APIRouter(
    prefix="/research",
    tags=["Research"],
)


@router.get(
    "/search",
    response_model=ExternalPaperSearchResponse,
)
def search_research_papers(
    q: str = Query(
        ...,
        min_length=2,
        description="Search query",
    ),
    limit: int = Query(
        10,
        ge=1,
        le=50,
    ),
    service: ResearchService = Depends(
        get_research_service,
    ),
):
    return service.search_papers(
        query=q,
        limit=limit,
    )