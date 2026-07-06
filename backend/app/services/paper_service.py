from math import ceil

from app.exceptions.custom_exceptions import (
    PaperNotFoundException,
    PaperPermissionDeniedException,
)
from app.repositories.paper_repository import PaperRepository
from app.schemas.research_paper import (
    PaginatedResearchPaperResponse,
    ResearchPaperCreate,
    ResearchPaperUpdate,
)


class PaperService:
    def __init__(self, repository: PaperRepository):
        self.repository = repository

    def create_paper(
        self,
        paper: ResearchPaperCreate,
        owner_id: int,
    ):
        return self.repository.create_paper(
            paper,
            owner_id,
        )

    def get_all_papers(
        self,
        page: int,
        size: int,
    ):
        papers = self.repository.get_all_papers(
            skip=(page - 1) * size,
            limit=size,
        )

        total = self.repository.count_papers()
        pages = ceil(total / size) if total > 0 else 0

        return PaginatedResearchPaperResponse(
            items=papers,
            page=page,
            size=size,
            total=total,
            pages=pages,
        )

    def search_papers(
        self,
        query: str,
        page: int,
        size: int,
    ):
        papers = self.repository.search_papers(
            query=query,
            skip=(page - 1) * size,
            limit=size,
        )

        total = self.repository.count_search_results(query)
        pages = ceil(total / size) if total > 0 else 0

        return PaginatedResearchPaperResponse(
            items=papers,
            page=page,
            size=size,
            total=total,
            pages=pages,
        )

    def get_paper_by_id(
        self,
        paper_id: int,
    ):
        paper = self.repository.get_paper_by_id(paper_id)

        if paper is None:
            raise PaperNotFoundException(paper_id)

        return paper

    def verify_paper_owner(
        self,
        paper,
        user_id: int,
    ):
        if paper.owner_id != user_id:
            raise PaperPermissionDeniedException()

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