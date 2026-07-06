from sqlalchemy.orm import Session

from app.models.research_paper import ResearchPaper
from app.schemas.research_paper import (
    ResearchPaperCreate,
    ResearchPaperUpdate,
)


class PaperRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_paper(
        self,
        paper: ResearchPaperCreate,
        owner_id: int,
    ):
        new_paper = ResearchPaper(
            title=paper.title,
            authors=paper.authors,
            abstract=paper.abstract,
            source=paper.source,
            url=str(paper.url) if paper.url else None,
            owner_id=owner_id,
        )

        self.db.add(new_paper)
        self.db.commit()
        self.db.refresh(new_paper)

        return new_paper

    def get_all_papers(
        self,
        page: int,
        size: int,
    ):
        return (
            self.db.query(ResearchPaper)
            .offset((page - 1) * size)
            .limit(size)
            .all()
        )

    def count_papers(self):
        return self.db.query(ResearchPaper).count()

    def get_paper_by_id(
        self,
        paper_id: int,
    ):
        return (
            self.db.query(ResearchPaper)
            .filter(ResearchPaper.id == paper_id)
            .first()
        )

    def update_paper(
        self,
        paper: ResearchPaper,
        updated_paper: ResearchPaperUpdate,
    ):
        update_data = updated_paper.model_dump(exclude_unset=True)

        if "url" in update_data:
            update_data["url"] = (
                str(update_data["url"])
                if update_data["url"]
                else None
            )

        for field, value in update_data.items():
            setattr(paper, field, value)

        self.db.commit()
        self.db.refresh(paper)

        return paper

    def delete_paper(
        self,
        paper: ResearchPaper,
    ):
        self.db.delete(paper)
        self.db.commit()