from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.research_paper import (
    ResearchPaperCreate,
    ResearchPaperUpdate,
    ResearchPaperResponse,
)
from app.services import paper_service

router = APIRouter(
    prefix="/papers",
    tags=["Research Papers"]
)


@router.post("/", response_model=ResearchPaperResponse)
def create_paper(
    paper: ResearchPaperCreate,
    db: Session = Depends(get_db),
):
    return paper_service.create_paper(db, paper)


@router.get("/", response_model=list[ResearchPaperResponse])
def get_all_papers(
    db: Session = Depends(get_db),
):
    return paper_service.get_all_papers(db)


@router.get("/{paper_id}", response_model=ResearchPaperResponse)
def get_paper(
    paper_id: int,
    db: Session = Depends(get_db),
):
    paper = paper_service.get_paper_by_id(db, paper_id)

    if paper is None:
        raise HTTPException(
            status_code=404,
            detail="Paper not found"
        )

    return paper


@router.put("/{paper_id}", response_model=ResearchPaperResponse)
def update_paper(
    paper_id: int,
    updated_paper: ResearchPaperUpdate,
    db: Session = Depends(get_db),
):
    paper = paper_service.get_paper_by_id(db, paper_id)

    if paper is None:
        raise HTTPException(
            status_code=404,
            detail="Paper not found"
        )

    return paper_service.update_paper(
        db,
        paper,
        updated_paper,
    )


@router.delete("/{paper_id}")
def delete_paper(
    paper_id: int,
    db: Session = Depends(get_db),
):
    paper = paper_service.get_paper_by_id(db, paper_id)

    if paper is None:
        raise HTTPException(
            status_code=404,
            detail="Paper not found"
        )

    paper_service.delete_paper(db, paper)

    return {
        "message": "Paper deleted successfully"
    }