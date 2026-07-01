from sqlalchemy.orm import Session

from app.models.research_paper import ResearchPaper
from app.schemas.research_paper import (
    ResearchPaperCreate,
    ResearchPaperUpdate,
)


def create_paper(
    db: Session,
    paper: ResearchPaperCreate,
):
    new_paper = ResearchPaper(
        title=paper.title,
        authors=paper.authors,
        abstract=paper.abstract,
        source=paper.source,
        url=str(paper.url) if paper.url else None,
    )

    db.add(new_paper)
    db.commit()
    db.refresh(new_paper)

    return new_paper


def get_all_papers(db: Session):
    return db.query(ResearchPaper).all()


def get_paper_by_id(
    db: Session,
    paper_id: int,
):
    return (
        db.query(ResearchPaper)
        .filter(ResearchPaper.id == paper_id)
        .first()
    )


def update_paper(
    db: Session,
    paper: ResearchPaper,
    updated_paper: ResearchPaperUpdate,
):
    paper.title = updated_paper.title
    paper.authors = updated_paper.authors
    paper.abstract = updated_paper.abstract
    paper.source = updated_paper.source
    paper.url = str(updated_paper.url) if updated_paper.url else None

    db.commit()
    db.refresh(paper)

    return paper


def delete_paper(
    db: Session,
    paper: ResearchPaper,
):
    db.delete(paper)
    db.commit()