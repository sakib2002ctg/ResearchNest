from sqlalchemy.orm import Session

from app.repositories import paper_repository
from app.schemas.research_paper import (
    ResearchPaperCreate,
    ResearchPaperUpdate,
)


def create_paper(
    db: Session,
    paper: ResearchPaperCreate,
):
    return paper_repository.create_paper(db, paper)


def get_all_papers(db: Session):
    return paper_repository.get_all_papers(db)


def get_paper_by_id(
    db: Session,
    paper_id: int,
):
    return paper_repository.get_paper_by_id(db, paper_id)


def update_paper(
    db: Session,
    paper,
    updated_paper: ResearchPaperUpdate,
):
    return paper_repository.update_paper(
        db,
        paper,
        updated_paper,
    )


def delete_paper(
    db: Session,
    paper,
):
    paper_repository.delete_paper(db, paper)