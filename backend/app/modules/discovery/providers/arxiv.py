from __future__ import annotations

import re
from typing import Literal

import feedparser

from app.modules.discovery.providers.base import (
    AsyncProvider,
    ProviderPaper,
    ProviderUnavailable,
)

_FIELDS = {
    "all": "all",
    "title": "ti",
    "author": "au",
    "id": "id",
}


class ArxivProvider(AsyncProvider):
    source = "arxiv"
    endpoint = "https://export.arxiv.org/api/query"
    min_request_interval = 3.0

    async def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        year_from: int | None = None,
        year_to: int | None = None,
        paper_type: str | None = None,
        field: Literal["all", "title", "author", "id"] = "all",
    ) -> list[ProviderPaper]:
        if not query.strip():
            return []
        limit, offset = self.validate_pagination(limit, offset)
        prefix = _FIELDS.get(field)
        if prefix is None:
            raise ValueError("Unsupported arXiv search field.")
        params = {
            "start": offset,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        if field == "id":
            params["id_list"] = query.strip()
        else:
            params["search_query"] = f"{prefix}:{query.strip()}"
        response = await self._get(self.endpoint, params=params)
        try:
            parsed = feedparser.parse(response.content)
            if parsed.bozo and not parsed.entries:
                raise ProviderUnavailable(self.source)
            papers = [
                self._paper(entry) for entry in parsed.entries if entry.get("title")
            ]
        except (AttributeError, TypeError, ValueError, KeyError):
            raise ProviderUnavailable(self.source) from None
        return self.filter_results(papers, year_from, year_to, paper_type)

    async def get_by_doi(self, doi: str) -> ProviderPaper | None:
        normalized = self.normalize_doi(doi)
        if not normalized:
            return None
        papers = await self.search(f'"{normalized}"', limit=10, field="all")
        return next((paper for paper in papers if paper.doi == normalized), None)

    async def get_by_id(self, arxiv_id: str) -> ProviderPaper | None:
        requested_id = self._identifier(arxiv_id)
        if not re.fullmatch(
            r"(?:\d{4}\.\d{4,5}|[a-z.-]+/\d{7})(?:v\d+)?", requested_id
        ):
            return None
        papers = await self.search(requested_id, limit=1, field="id")
        requested_base = re.sub(r"v\d+$", "", requested_id)
        return next(
            (
                paper
                for paper in papers
                if paper.external_id
                and re.sub(r"v\d+$", "", paper.external_id) == requested_base
            ),
            None,
        )

    @staticmethod
    def _identifier(value: str) -> str:
        identifier = value.strip().rstrip("/")
        if "/abs/" in identifier:
            return identifier.split("/abs/", 1)[-1]
        return identifier.removeprefix("arXiv:")

    @staticmethod
    def _paper(entry: dict) -> ProviderPaper:
        external_id = ArxivProvider._identifier(str(entry.get("id") or "")) or None
        links = entry.get("links", [])
        url = next(
            (item.get("href") for item in links if item.get("rel") == "alternate"),
            entry.get("id"),
        )
        published = str(entry.get("published") or "")[:10] or None
        doi = entry.get("arxiv_doi") or entry.get("doi")
        categories = entry.get("tags") or []
        category = categories[0].get("term") if categories else None
        return ProviderPaper(
            title=" ".join(str(entry.get("title") or "").split()),
            authors=[
                str(author.get("name", "")).strip()
                for author in entry.get("authors", [])
                if author.get("name")
            ],
            abstract=str(entry.get("summary") or "").strip() or None,
            doi=AsyncProvider.normalize_doi(str(doi)) if doi else None,
            publication_date=published,
            url=str(url) if url else None,
            source="arxiv",
            external_id=external_id,
            paper_type=f"preprint:{category}" if category else "preprint",
            citation_count=None,
        )
