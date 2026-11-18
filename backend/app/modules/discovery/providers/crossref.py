from __future__ import annotations

from typing import Literal
from urllib.parse import quote

from app.modules.discovery.providers.base import AsyncProvider, ProviderPaper


class CrossrefProvider(AsyncProvider):
    source = "crossref"
    endpoint = "https://api.crossref.org"

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
            paper = await self.get_by_doi(query)
            return self.filter_results(
                [paper] if paper and not offset else [], year_from, year_to, paper_type
            )
        params: dict[str, str | int] = {"rows": limit, "offset": offset}
        params[
            (
                "query.title"
                if field == "title"
                else "query.author" if field == "author" else "query"
            )
        ] = query.strip()
        if year_from is not None or year_to is not None:
            filters = []
            if year_from is not None:
                filters.append(f"from-pub-date:{year_from}-01-01")
            if year_to is not None:
                filters.append(f"until-pub-date:{year_to}-12-31")
            params["filter"] = ",".join(filters)
        if paper_type:
            params["filter"] = ",".join(
                value
                for value in (
                    str(params.get("filter", "")),
                    f"type:{paper_type.strip()}",
                )
                if value
            )
        response = await self._get(f"{self.endpoint}/works", params=params)
        payload = self._json(response)
        message = payload.get("message", {}) if isinstance(payload, dict) else {}
        items = message.get("items", []) if isinstance(message, dict) else []
        papers = [
            self._paper(item) for item in self._records(items) if item.get("title")
        ]
        return self.filter_results(papers, year_from, year_to, paper_type)

    async def get_by_doi(self, doi: str) -> ProviderPaper | None:
        normalized = self.normalize_doi(doi)
        if not normalized:
            return None
        response = await self._get(
            f"{self.endpoint}/works/{quote(normalized, safe='')}",
            allow_not_found=True,
        )
        if response.status_code == 404:
            return None
        payload = self._json(response)
        message = payload.get("message") if isinstance(payload, dict) else None
        return self._paper(message) if isinstance(message, dict) else None

    async def get_by_id(self, external_id: str) -> ProviderPaper | None:
        return await self.get_by_doi(external_id)

    @classmethod
    def _paper(cls, item: dict) -> ProviderPaper:
        authors = []
        for author in cls._records(item.get("author")):
            name = " ".join(
                str(part).strip()
                for part in (author.get("given"), author.get("family"))
                if part
            )
            if name:
                authors.append(name)
        date_parts = []
        for field in ("published", "published-print", "issued"):
            date = item.get(field)
            parts = date.get("date-parts") if isinstance(date, dict) else None
            if isinstance(parts, list) and parts and isinstance(parts[0], list):
                date_parts = parts[0]
                break
        date = (
            "-".join(
                str(part).zfill(2) if index else str(part)
                for index, part in enumerate(date_parts)
            )
            if date_parts
            else None
        )
        titles = item.get("title")
        title = titles[0] if isinstance(titles, list) and titles else ""
        abstract = str(item.get("abstract") or "")
        abstract = (
            " ".join(abstract.replace("<jats:p>", "").replace("</jats:p>", "").split())
            or None
        )
        return ProviderPaper(
            title=str(title).strip(),
            authors=authors,
            abstract=abstract,
            doi=cls.normalize_doi(str(item["DOI"])) if item.get("DOI") else None,
            publication_date=date,
            url=str(item.get("URL")) if item.get("URL") else None,
            source="crossref",
            external_id=str(item.get("DOI")) if item.get("DOI") else None,
            paper_type=str(item.get("type")) if item.get("type") else None,
            citation_count=cls._count(item.get("is-referenced-by-count")),
        )

    @staticmethod
    def _count(value: object) -> int | None:
        try:
            return max(0, int(value)) if value is not None else None
        except (TypeError, ValueError):
            return None
