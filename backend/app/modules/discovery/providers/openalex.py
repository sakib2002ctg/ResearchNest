from __future__ import annotations

import re
from typing import Literal
from urllib.parse import quote

from app.modules.discovery.providers.base import AsyncProvider, ProviderPaper


class OpenAlexProvider(AsyncProvider):
    source = "openalex"
    endpoint = "https://api.openalex.org"
    _page_size = 100

    def __init__(self, *, api_key: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._api_key = api_key.strip() if api_key else None

    def _headers(self) -> dict[str, str] | None:
        return {"Authorization": f"Bearer {self._api_key}"} if self._api_key else None

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
        page_size = limit if offset % limit == 0 else self._page_size
        page, skip = divmod(offset, page_size)
        params: dict[str, str | int] = {
            "per_page": page_size,
            "page": page + 1,
        }
        filters: list[str] = []
        if field == "title":
            filters.append(f"title.search:{query.strip()}")
        elif field == "author":
            filters.append(f"raw_author_name.search:{query.strip()}")
        else:
            params["search"] = query.strip()
        if year_from is not None:
            filters.append(f"from_publication_date:{year_from}-01-01")
        if year_to is not None:
            filters.append(f"to_publication_date:{year_to}-12-31")
        if paper_type:
            filters.append(f"type:{paper_type.strip()}")
        if filters:
            params["filter"] = ",".join(filters)
        results = await self._get_works(params)
        selected = results[skip : skip + limit]
        if len(results) == page_size and skip + limit > page_size:
            params["page"] = page + 2
            next_page = await self._get_works(params)
            selected.extend(next_page[: limit - len(selected)])
        papers = [
            self._paper(work)
            for work in selected
            if isinstance(work, dict) and work.get("title")
        ]
        return self.filter_results(papers, year_from, year_to, paper_type)

    async def _get_works(self, params: dict[str, str | int]) -> list:
        response = await self._get(
            f"{self.endpoint}/works", params=params, headers=self._headers()
        )
        payload = self._json(response)
        results = payload.get("results") if isinstance(payload, dict) else None
        return results if isinstance(results, list) else []

    async def get_by_doi(self, doi: str) -> ProviderPaper | None:
        normalized = self.normalize_doi(doi)
        if not normalized:
            return None
        response = await self._get(
            f"{self.endpoint}/works/https://doi.org/{quote(normalized, safe='')}",
            headers=self._headers(),
            allow_not_found=True,
        )
        if response.status_code == 404:
            return None
        payload = self._json(response)
        return self._paper(payload) if isinstance(payload, dict) else None

    async def get_by_id(self, external_id: str) -> ProviderPaper | None:
        value = external_id.strip().rstrip("/").rsplit("/", 1)[-1].upper()
        if not re.fullmatch(r"W[0-9]+", value):
            return None
        response = await self._get(
            f"{self.endpoint}/works/{value}",
            headers=self._headers(),
            allow_not_found=True,
        )
        if response.status_code == 404:
            return None
        payload = self._json(response)
        return self._paper(payload) if isinstance(payload, dict) else None

    @classmethod
    def _paper(cls, work: dict) -> ProviderPaper:
        authors = [
            str(authorship["author"].get("display_name") or "").strip()
            for authorship in cls._records(work.get("authorships"))
            if isinstance(authorship.get("author"), dict)
        ]
        doi = work.get("doi")
        abstract = cls._abstract(work.get("abstract_inverted_index"))
        location = work.get("primary_location") or {}
        landing = (
            location.get("landing_page_url") if isinstance(location, dict) else None
        )
        date = work.get("publication_date") or (
            f"{work.get('publication_year')}-01-01"
            if work.get("publication_year")
            else None
        )
        return ProviderPaper(
            title=str(work.get("title") or "").strip(),
            authors=[name for name in authors if name],
            abstract=abstract,
            doi=cls.normalize_doi(str(doi)) if doi else None,
            publication_date=str(date) if date else None,
            url=str(landing or work.get("id")) if landing or work.get("id") else None,
            source="openalex",
            external_id=str(work.get("id")) if work.get("id") else None,
            paper_type=str(work.get("type")) if work.get("type") else None,
            citation_count=cls._count(work.get("cited_by_count")),
        )

    @staticmethod
    def _count(value: object) -> int | None:
        try:
            return max(0, int(value)) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _abstract(index: object) -> str | None:
        if not isinstance(index, dict):
            return None
        positions: dict[int, str] = {}
        for word, offsets in index.items():
            if isinstance(offsets, list):
                for offset in offsets:
                    if isinstance(offset, int) and offset >= 0:
                        positions[offset] = str(word)
        if not positions:
            return None
        return " ".join(positions[position] for position in sorted(positions))
