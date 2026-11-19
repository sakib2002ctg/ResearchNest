from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from app.modules.discovery.providers.base import (
    AsyncProvider,
    ProviderCitation,
    ProviderPaper,
)

_FIELDS = (
    "paperId,title,abstract,authors,year,publicationDate,"
    "externalIds,url,citationCount,publicationTypes"
)
_DOI_FIELDS = f"{_FIELDS},citations.title,citations.url,citations.externalIds"


class SemanticScholarProvider(AsyncProvider):
    source = "semantic_scholar"
    endpoint = "https://api.semanticscholar.org/graph/v1"
    recommendation_endpoint = "https://api.semanticscholar.org/recommendations/v1"
    min_request_interval = 1.0

    def __init__(self, *, api_key: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key.strip() if api_key and api_key.strip() else None

    def _headers(self) -> dict[str, str] | None:
        return {"x-api-key": self._api_key} if self._api_key else None

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
        if field == "id":
            paper = (
                await self.get_by_doi(query)
                if self.normalize_doi(query).startswith("10.")
                else await self.get_by_id(query)
            )
            return self.filter_results(
                [paper] if paper and not offset else [], year_from, year_to, paper_type
            )
        params: dict[str, str | int] = {
            "query": query.strip(),
            "limit": limit,
            "offset": offset,
            "fields": _FIELDS,
        }
        if year_from is not None or year_to is not None:
            params["year"] = f"{year_from or ''}-{year_to or ''}"
        if paper_type:
            params["publicationTypes"] = paper_type.strip()
        response = await self._get(
            f"{self.endpoint}/paper/search", params=params, headers=self._headers()
        )
        payload = self._json(response)
        items = payload.get("data", []) if isinstance(payload, dict) else []
        papers = [
            self._paper(item) for item in self._records(items) if item.get("title")
        ]
        if field == "author":
            papers = [
                paper
                for paper in papers
                if any(
                    query.casefold().strip() in name.casefold()
                    for name in paper.authors
                )
            ]
        elif field == "title":
            papers = [
                paper
                for paper in papers
                if query.casefold().strip() in paper.title.casefold()
            ]
        return self.filter_results(papers, year_from, year_to, paper_type)

    async def get_by_doi(self, doi: str) -> ProviderPaper | None:
        normalized = self.normalize_doi(doi)
        if not normalized:
            return None
        response = await self._get(
            f"{self.endpoint}/paper/DOI:{quote(normalized, safe='')}",
            params={"fields": _DOI_FIELDS},
            headers=self._headers(),
            allow_not_found=True,
        )
        if response.status_code == 404:
            return None
        payload = self._json(response)
        if not isinstance(payload, dict):
            return None
        paper = self._paper(payload)
        paper.citation_links = [
            self._citation_link(self._paper(item))
            for item in self._records(payload.get("citations"))[:20]
            if item.get("title")
        ]
        return paper

    async def get_by_id(self, external_id: str) -> ProviderPaper | None:
        value = external_id.strip()
        if not value:
            return None
        response = await self._get(
            f"{self.endpoint}/paper/{quote(value, safe='')}",
            params={"fields": _FIELDS},
            headers=self._headers(),
            allow_not_found=True,
        )
        if response.status_code == 404:
            return None
        payload = self._json(response)
        return self._paper(payload) if isinstance(payload, dict) else None

    async def recommendations(
        self, paper_id: str, limit: int = 10
    ) -> list[ProviderPaper]:
        if not paper_id.strip():
            return []
        limit = max(1, min(limit, 50))
        identifier = quote(paper_id.strip(), safe="")
        response = await self._get(
            f"{self.recommendation_endpoint}/papers/forpaper/{identifier}",
            params={"limit": limit, "fields": _FIELDS},
            headers=self._headers(),
        )
        payload = self._json(response)
        items = (
            payload.get("recommendedPapers", []) if isinstance(payload, dict) else []
        )
        return [self._paper(item) for item in self._records(items) if item.get("title")]

    async def citations(self, paper_id: str, limit: int = 20) -> list[ProviderPaper]:
        if not paper_id.strip():
            return []
        limit = max(1, min(limit, 50))
        response = await self._get(
            f"{self.endpoint}/paper/{quote(paper_id.strip(), safe='')}/citations",
            params={"limit": limit, "fields": _FIELDS},
            headers=self._headers(),
        )
        payload = self._json(response)
        items = payload.get("data", []) if isinstance(payload, dict) else []
        result = []
        for item in self._records(items):
            paper = item.get("citingPaper")
            if isinstance(paper, dict) and paper.get("title"):
                result.append(self._paper(paper))
        return result

    async def citation_links(
        self, paper_id: str, limit: int = 20
    ) -> list[ProviderCitation]:
        papers = await self.citations(paper_id, limit)
        return [self._citation_link(paper) for paper in papers]

    @staticmethod
    def _citation_link(paper: ProviderPaper) -> ProviderCitation:
        return ProviderCitation(
            title=paper.title, url=paper.url, doi=paper.doi, source=paper.source
        )

    @classmethod
    def _paper(cls, item: dict) -> ProviderPaper:
        external = item.get("externalIds")
        external = external if isinstance(external, dict) else {}
        authors = cls._records(item.get("authors"))
        year = item.get("publicationDate") or item.get("year")
        types = item.get("publicationTypes")
        return ProviderPaper(
            title=str(item.get("title") or "").strip(),
            authors=[
                str(author.get("name")).strip()
                for author in authors
                if author.get("name")
            ],
            abstract=str(item.get("abstract") or "").strip() or None,
            doi=(
                cls.normalize_doi(str(external["DOI"])) if external.get("DOI") else None
            ),
            publication_date=str(year) if year else None,
            url=str(item.get("url")) if item.get("url") else None,
            source="semantic_scholar",
            external_id=str(item.get("paperId")) if item.get("paperId") else None,
            paper_type=(
                ", ".join(value for value in types if isinstance(value, str)) or None
                if isinstance(types, list)
                else None
            ),
            citation_count=cls._count(item.get("citationCount")),
        )

    @staticmethod
    def _count(value: object) -> int | None:
        try:
            return max(0, int(value)) if value is not None else None
        except (TypeError, ValueError):
            return None
