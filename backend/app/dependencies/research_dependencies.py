from app.clients.arxiv_client import ArxivClient
from app.services.research_service import ResearchService


def get_research_service() -> ResearchService:
    provider = ArxivClient()
    return ResearchService(provider)
