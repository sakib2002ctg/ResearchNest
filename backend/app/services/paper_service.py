from app.exceptions.custom_exceptions import PaperNotFoundException
from app.repositories.paper_repository import PaperRepository
from app.schemas.research_paper import (
    ResearchPaperCreate,
    ResearchPaperUpdate,
)


class PaperService:
    def __init__(self, repository: PaperRepository):
        self.repository = repository

    def create_paper(
        self,
        paper: ResearchPaperCreate,
    ):
        return self.repository.create_paper(paper)

    def get_all_papers(self):
        return self.repository.get_all_papers()

    def get_paper_by_id(
        self,
        paper_id: int,
    ):
        paper = self.repository.get_paper_by_id(paper_id)

        if paper is None:
            raise PaperNotFoundException(paper_id)

        return paper

    def update_paper(
        self,
        paper,
        updated_paper: ResearchPaperUpdate,
    ):
        return self.repository.update_paper(
            paper,
            updated_paper,
        )

    def delete_paper(
        self,
        paper,
    ):
        self.repository.delete_paper(paper)