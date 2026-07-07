from fastapi import APIRouter, Depends, Query

from app.dependencies.current_user import get_current_user
from app.dependencies.paper_dependencies import get_paper_service
from app.models.user import User
from app.schemas.research_paper import (
    PaginatedResearchPaperResponse,
    ResearchPaperCreate,
    ResearchPaperResponse,
    ResearchPaperUpdate,
)
from app.services.paper_service import PaperService

router = APIRouter(
    prefix="/papers",
    tags=["Research Papers"],
)


@router.post("/", response_model=ResearchPaperResponse)
def create_paper(
    paper: ResearchPaperCreate,
    current_user: User = Depends(get_current_user),
    service: PaperService = Depends(get_paper_service),
):
    return service.create_paper(
        paper,
        current_user.id,
    )


@router.get("/", response_model=PaginatedResearchPaperResponse)
def get_all_papers(
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    service: PaperService = Depends(get_paper_service),
):
    return service.get_all_papers(
        page,
        size,
    )


# -------------------- SEARCH -------------------- #
@router.get("/search", response_model=PaginatedResearchPaperResponse)
def search_papers(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    service: PaperService = Depends(get_paper_service),
):
    return service.search_papers(
        query=q,
        page=page,
        size=size,
    )


@router.get("/{paper_id}", response_model=ResearchPaperResponse)
def get_paper(
    paper_id: int,
    service: PaperService = Depends(get_paper_service),
):
    return service.get_paper_by_id(paper_id)


@router.put("/{paper_id}", response_model=ResearchPaperResponse)
def update_paper(
    paper_id: int,
    updated_paper: ResearchPaperUpdate,
    current_user: User = Depends(get_current_user),
    service: PaperService = Depends(get_paper_service),
):
    paper = service.get_paper_by_id(paper_id)

    service.verify_paper_owner(
        paper,
        current_user.id,
    )

    return service.update_paper(
        paper,
        updated_paper,
    )


@router.delete("/{paper_id}")
def delete_paper(
    paper_id: int,
    current_user: User = Depends(get_current_user),
    service: PaperService = Depends(get_paper_service),
):
    paper = service.get_paper_by_id(paper_id)

    service.verify_paper_owner(
        paper,
        current_user.id,
    )

    service.delete_paper(paper)

    return {"message": "Paper deleted successfully"}
