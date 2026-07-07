from app.clients.base import ResearchProvider
from app.schemas.external_paper import ExternalPaperSearchResponse


class ResearchService:
    """
    Service layer responsible for searching external research papers.
    """

    def __init__(
        self,
        provider: ResearchProvider,
    ):
        self.provider = provider

    def search_papers(
        self,
        query: str,
        limit: int = 10,
    ) -> ExternalPaperSearchResponse:
        return self.provider.search(
            query=query,
            limit=limit,
        )
