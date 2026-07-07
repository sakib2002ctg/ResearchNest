from abc import ABC, abstractmethod

from app.schemas.external_paper import ExternalPaperSearchResponse


class ResearchProvider(ABC):
    """
    Abstract base class for all external research providers.

    Every provider (arXiv, Semantic Scholar, PubMed, etc.)
    must implement this interface.
    """

    @abstractmethod
    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> ExternalPaperSearchResponse:
        """
        Search research papers from an external provider.
        """
        raise NotImplementedError