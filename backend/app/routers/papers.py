from fastapi import APIRouter, Depends

from app.dependencies.paper_dependencies import get_paper_service
from app.schemas.research_paper import (
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
    service: PaperService = Depends(get_paper_service),
):
    return service.create_paper(paper)


@router.get("/", response_model=list[ResearchPaperResponse])
def get_all_papers(
    service: PaperService = Depends(get_paper_service),
):
    return service.get_all_papers()


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
    service: PaperService = Depends(get_paper_service),
):
    paper = service.get_paper_by_id(paper_id)

    return service.update_paper(
        paper,
        updated_paper,
    )


@router.delete("/{paper_id}")
def delete_paper(
    paper_id: int,
    service: PaperService = Depends(get_paper_service),
):
    paper = service.get_paper_by_id(paper_id)

    service.delete_paper(paper)

    return {
        "message": "Paper deleted successfully"
    }