import feedparser
import httpx

from app.clients.base import ResearchProvider
from app.schemas.external_paper import (
    ExternalPaper,
    ExternalPaperSearchResponse,
)


class ArxivClient(ResearchProvider):
    BASE_URL = "http://export.arxiv.org/api/query"

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> ExternalPaperSearchResponse:

        response = httpx.get(
            self.BASE_URL,
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": limit,
            },
            timeout=30,
        )

        response.raise_for_status()

        feed = feedparser.parse(response.text)

        papers = []

        for entry in feed.entries:
            papers.append(
                ExternalPaper(
                    title=entry.title.strip(),
                    authors=[
                        author.name
                        for author in entry.authors
                    ],
                    abstract=entry.summary.strip(),
                    url=entry.link,
                    source="arXiv",
                )
            )

        return ExternalPaperSearchResponse(
            papers=papers,
            total=len(papers),
        )