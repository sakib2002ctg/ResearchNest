from app.clients.base import ResearchProvider
from app.schemas.external_paper import (
    ExternalPaper,
    ExternalPaperSearchResponse,
)
from app.services.research_service import ResearchService


class FakeResearchProvider(ResearchProvider):
    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> ExternalPaperSearchResponse:
        return ExternalPaperSearchResponse(
            papers=[
                ExternalPaper(
                    title="Attention Is All You Need",
                    authors=["Ashish Vaswani"],
                    abstract="Transformer architecture",
                    url="https://arxiv.org/abs/1706.03762",
                    source="arXiv",
                )
            ],
            total=1,
        )


def test_search_papers_returns_response():
    service = ResearchService(
        FakeResearchProvider(),
    )

    result = service.search_papers(
        query="transformer",
    )

    assert isinstance(
        result,
        ExternalPaperSearchResponse,
    )

    assert result.total == 1


def test_search_papers_returns_paper():
    service = ResearchService(
        FakeResearchProvider(),
    )

    result = service.search_papers(
        query="transformer",
    )

    paper = result.papers[0]

    assert paper.title == "Attention Is All You Need"
    assert paper.source == "arXiv"


def test_search_papers_authors():
    service = ResearchService(
        FakeResearchProvider(),
    )

    result = service.search_papers(
        query="transformer",
    )

    assert result.papers[0].authors == [
        "Ashish Vaswani"
    ]


def test_search_papers_limit_argument():
    provider = FakeResearchProvider()

    service = ResearchService(provider)

    result = service.search_papers(
        query="ai",
        limit=5,
    )

    assert result.total == 1


def test_search_returns_external_response():
    service = ResearchService(
        FakeResearchProvider(),
    )

    response = service.search_papers(
        query="machine learning",
    )

    assert len(response.papers) == 1