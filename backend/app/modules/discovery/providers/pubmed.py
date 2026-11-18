from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Literal

import httpx

from app.modules.discovery.providers.base import (
    AsyncProvider,
    ProviderPaper,
    ProviderUnavailable,
)


class PubMedProvider(AsyncProvider):
    source = "pubmed"
    endpoint = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    min_request_interval = 0.35

    def __init__(
        self, *, email: str | None = None, api_key: str | None = None, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._email = email.strip() if email and email.strip() else None
        self._api_key = api_key.strip() if api_key and api_key.strip() else None

    def _params(self, values: dict[str, str | int]) -> dict[str, str | int]:
        params = dict(values)
        if self._email:
            params["email"] = self._email
        if self._api_key:
            params["api_key"] = self._api_key
        params.setdefault("tool", "ResearchNest")
        return params

    async def _entrez(
        self, operation: str, params: dict[str, str | int]
    ) -> httpx.Response:
        url = f"{self.endpoint}/{operation}.fcgi"
        values = self._params(params)
        if self._api_key:
            return await self._request("POST", url, data=values)
        return await self._get(url, params=values)

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
        term = query.strip()
        if field == "id":
            paper = (
                await self.get_by_doi(query)
                if self.normalize_doi(query).startswith("10.")
                else await self.get_by_id(query)
            )
            return self.filter_results(
                [paper] if paper and not offset else [], year_from, year_to, paper_type
            )
        if field == "title":
            term = f"{term}[Title]"
        elif field == "author":
            term = f"{term}[Author]"
        elif field != "all":
            raise ValueError("Unsupported PubMed search field.")
        params: dict[str, str | int] = {
            "db": "pubmed",
            "term": term,
            "retmax": limit,
            "retstart": offset,
            "retmode": "json",
            "sort": "relevance",
        }
        if year_from is not None:
            params["mindate"] = year_from
        if year_to is not None:
            params["maxdate"] = year_to
        if year_from is not None or year_to is not None:
            params["datetype"] = "pdat"
        response = await self._entrez("esearch", params)
        payload = self._json(response)
        result = payload.get("esearchresult") if isinstance(payload, dict) else None
        ids = result.get("idlist") if isinstance(result, dict) else None
        if not isinstance(ids, list):
            raise ProviderUnavailable(self.source)
        identifiers = [
            value
            for value in ids
            if isinstance(value, str) and value.isascii() and value.isdecimal()
        ]
        if not identifiers:
            return []
        papers = await self._fetch(identifiers[:limit])
        return self.filter_results(papers, year_from, year_to, paper_type)

    async def _fetch(self, identifiers: list[str]) -> list[ProviderPaper]:
        fetch = await self._entrez(
            "efetch", {"db": "pubmed", "id": ",".join(identifiers), "retmode": "xml"}
        )
        papers = {paper.external_id: paper for paper in self._parse_xml(fetch.content)}
        return [
            papers[identifier] for identifier in identifiers if identifier in papers
        ]

    async def get_by_doi(self, doi: str) -> ProviderPaper | None:
        normalized = self.normalize_doi(doi)
        if not normalized:
            return None
        papers = await self.search(f'"{normalized}"[AID]', limit=10)
        return next((paper for paper in papers if paper.doi == normalized), None)

    async def get_by_id(self, external_id: str) -> ProviderPaper | None:
        wanted = external_id.strip()
        if not wanted.isascii() or not wanted.isdecimal():
            return None
        papers = await self._fetch([wanted])
        return papers[0] if papers else None

    def _parse_xml(self, content: bytes) -> list[ProviderPaper]:
        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            raise ProviderUnavailable(self.source) from None
        results: list[ProviderPaper] = []
        for article in root.findall(".//PubmedArticle"):
            citation = article.find(".//MedlineCitation")
            record = citation.find("Article") if citation is not None else None
            if record is None:
                continue
            title = self._element_text(record.find("ArticleTitle"))
            if not title:
                continue
            authors = []
            for author in record.findall(".//Author"):
                collective = self._element_text(author.find("CollectiveName"))
                last = self._element_text(author.find("LastName"))
                initials = self._element_text(author.find("Initials"))
                name = collective or " ".join(part for part in (last, initials) if part)
                if name:
                    authors.append(name)
            abstract = (
                " ".join(
                    text
                    for node in record.findall(".//Abstract/AbstractText")
                    if (text := self._element_text(node))
                )
                or None
            )
            pmid = (
                self._element_text(citation.find("PMID"))
                if citation is not None
                else None
            )
            pub_date = record.find(".//JournalIssue/PubDate")
            published = (
                self._element_text(pub_date.find("Year"))
                if pub_date is not None
                else None
            )
            if pub_date is not None and not published:
                published = self._element_text(pub_date.find("MedlineDate"))
            doi = next(
                (
                    self._element_text(identifier)
                    for identifier in article.findall(".//ArticleId")
                    if identifier.attrib.get("IdType", "").casefold() == "doi"
                ),
                None,
            )
            if not doi:
                doi = next(
                    (
                        self._element_text(identifier)
                        for identifier in record.findall("ELocationID")
                        if identifier.get("EIdType") == "doi"
                    ),
                    None,
                )
            publication_types = [
                self._element_text(node)
                for node in record.findall("./PublicationTypeList/PublicationType")
            ]
            results.append(
                ProviderPaper(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    doi=self.normalize_doi(doi) if doi else None,
                    publication_date=published,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
                    source="pubmed",
                    external_id=pmid,
                    paper_type=", ".join(value for value in publication_types if value)
                    or None,
                    citation_count=None,
                )
            )
        return results

    @classmethod
    def _element_text(cls, element: ET.Element | None) -> str:
        if element is None:
            return ""
        return " ".join("".join(element.itertext()).split())
