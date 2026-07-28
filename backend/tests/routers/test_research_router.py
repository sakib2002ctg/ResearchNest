from app.dependencies.research_dependencies import (
    get_research_service,
)
from app.schemas.external_paper import (
    ExternalPaper,
    ExternalPaperSearchResponse,
)


class FakeResearchService:
    def search_papers(
        self,
        query: str,
        limit: int = 10,
    ):
        if query == "empty":
            return ExternalPaperSearchResponse(
                papers=[],
                total=0,
            )

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


def override_research_service():
    return FakeResearchService()


def test_search_success(client):
    client.app.dependency_overrides[get_research_service] = override_research_service

    response = client.get("/api/v1/research/search?q=transformer")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert len(data["papers"]) == 1


def test_search_empty(client):
    client.app.dependency_overrides[get_research_service] = override_research_service

    response = client.get("/api/v1/research/search?q=empty")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 0
    assert data["papers"] == []


def test_query_validation(client):
    response = client.get("/api/v1/research/search?q=a")

    assert response.status_code == 422


def test_limit_validation_low(client):
    response = client.get("/api/v1/research/search?q=test&limit=0")

    assert response.status_code == 422


def test_limit_validation_high(client):
    response = client.get("/api/v1/research/search?q=test&limit=100")

    assert response.status_code == 422


def test_response_schema(client):
    client.app.dependency_overrides[get_research_service] = override_research_service

    response = client.get("/api/v1/research/search?q=transformer")

    assert response.status_code == 200

    paper = response.json()["papers"][0]

    assert "title" in paper
    assert "authors" in paper
    assert "abstract" in paper
    assert "url" in paper
    assert "source" in paper
