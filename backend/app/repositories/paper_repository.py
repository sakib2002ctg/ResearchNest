from sqlalchemy import func, or_
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
    ) -> ResearchPaper:
        db_paper = ResearchPaper(
            **paper.model_dump(),
            owner_id=owner_id,
        )

        self.db.add(db_paper)
        self.db.commit()
        self.db.refresh(db_paper)

        return db_paper

    def get_paper_by_id(self, paper_id: int) -> ResearchPaper | None:
        return (
            self.db.query(ResearchPaper)
            .filter(ResearchPaper.id == paper_id)
            .first()
        )

    def get_all_papers(
        self,
        skip: int = 0,
        limit: int = 10,
    ) -> list[ResearchPaper]:
        return (
            self.db.query(ResearchPaper)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_papers(self) -> int:
        return self.db.query(func.count(ResearchPaper.id)).scalar()

    def search_papers(
        self,
        query: str,
        skip: int = 0,
        limit: int = 10,
    ) -> list[ResearchPaper]:
        search = f"%{query}%"

        return (
            self.db.query(ResearchPaper)
            .filter(
                or_(
                    ResearchPaper.title.ilike(search),
                    ResearchPaper.authors.ilike(search),
                    ResearchPaper.abstract.ilike(search),
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_search_results(self, query: str) -> int:
        search = f"%{query}%"

        return (
            self.db.query(func.count(ResearchPaper.id))
            .filter(
                or_(
                    ResearchPaper.title.ilike(search),
                    ResearchPaper.authors.ilike(search),
                    ResearchPaper.abstract.ilike(search),
                )
            )
            .scalar()
        )

    def update_paper(
        self,
        db_paper: ResearchPaper,
        paper_update: ResearchPaperUpdate,
    ) -> ResearchPaper:
        update_data = paper_update.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_paper, field, value)

        self.db.commit()
        self.db.refresh(db_paper)

        return db_paper

    def delete_paper(self, db_paper: ResearchPaper) -> None:
        self.db.delete(db_paper)
        self.db.commit()