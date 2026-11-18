import asyncio
import hashlib
import json
import re
import unicodedata
from collections.abc import Awaitable
from datetime import date
from typing import TypeVar

from pydantic import HttpUrl, ValidationError

from app.modules.discovery.cache import SearchCache, SearchSnapshot
from app.modules.discovery.providers import (
    DiscoveryProvider,
    ProviderPaper,
    ProviderUnavailable,
)
from app.modules.discovery.schemas import (
    CitationLink,
    DiscoveryPaper,
    DiscoverySearchRequest,
    DiscoverySearchResponse,
    DiscoverySource,
    SaveToLibraryRequest,
)

PROVIDER_WINDOW = 50
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[^\s?#\\]+", re.ASCII)
T = TypeVar("T")


class PaperNotFound(LookupError):
    pass


class InvalidPaperReference(ValueError):
    pass


def normalize_doi(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip().casefold()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if value.startswith(prefix):
            value = value.removeprefix(prefix).strip()
            break
    if (
        len(value) <= 255
        and value.isprintable()
        and DOI_PATTERN.fullmatch(value)
        and all(part not in {".", ".."} for part in value.split("/"))
    ):
        return value
    return None


def _identity(value: str) -> str:
    text = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(
        "".join(
            char if unicodedata.category(char)[0] in "LMN" else " " for char in text
        ).split()
    )


def _publication_date(value: str | None) -> date | None:
    if not value:
        return None
    value = value[:10]
    if len(value) == 4:
        value += "-01-01"
    elif len(value) == 7:
        value += "-01"
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _publication_type(value: str | None) -> str | None:
    if not value:
        return None
    compact = re.sub(r"[^a-z]", "", value.lower())
    for category, markers in (
        ("review", ("review", "metaanalysis")),
        ("preprint", ("preprint", "postedcontent")),
        ("book_chapter", ("bookchapter", "bookpart", "booksection")),
        ("conference", ("conference", "proceedings", "proceeding")),
        ("book", ("book", "monograph")),
        ("article", ("article", "editorial", "letter")),
    ):
        if any(marker in compact for marker in markers):
            return category
    return "other"


def _url(value: str | None) -> HttpUrl | None:
    if not value:
        return None
    try:
        url = HttpUrl(value)
    except ValidationError:
        return None
    return None if url.username or url.password else url


def _display_text(value: str, limit: int) -> str:
    return " ".join(value.replace("\x00", "").split())[:limit]


def _normalize(paper: ProviderPaper) -> DiscoveryPaper | None:
    title = _display_text(paper.title, 500)
    if not title:
        return None
    citations = []
    for link in paper.citation_links[:20]:
        doi, url = normalize_doi(link.doi), _url(link.url)
        title_or_id = _display_text(link.title or doi or "", 500)
        if title_or_id:
            citations.append(
                CitationLink(title=title_or_id, doi=doi, url=url, source=link.source)
            )
    external_id = paper.external_id
    if external_id and (len(external_id) > 255 or not external_id.isprintable()):
        external_id = None
    return DiscoveryPaper(
        title=title,
        authors=[
            clean for name in paper.authors[:100] if (clean := _display_text(name, 250))
        ],
        abstract=_display_text(paper.abstract or "", 20000) or None,
        doi=normalize_doi(paper.doi),
        publication_date=_publication_date(paper.publication_date),
        url=_url(paper.url),
        source=paper.source,
        sources=[paper.source],
        external_id=external_id,
        paper_type=_publication_type(paper.paper_type),
        citation_count=paper.citation_count,
        citation_links=citations,
    )


def _same_paper(a: DiscoveryPaper, b: DiscoveryPaper) -> bool:
    if a.doi and b.doi:
        return a.doi == b.doi
    if a.source == b.source and a.external_id and a.external_id == b.external_id:
        return True
    title = _identity(a.title)
    if not title or title != _identity(b.title):
        return False
    if a.publication_date and b.publication_date:
        if abs(a.publication_date.year - b.publication_date.year) > 1:
            return False
    return bool(
        {_identity(name) for name in a.authors if _identity(name)}.intersection(
            _identity(name) for name in b.authors
        )
    )


def _merge(a: DiscoveryPaper, b: DiscoveryPaper) -> DiscoveryPaper:
    # Keep the save reference attached to the provider that supplied its DOI.
    primary = b if b.doi and not a.doi else a
    citations = {}
    for link in (*a.citation_links, *b.citation_links):
        citations.setdefault(link.doi or str(link.url or link.title), link)
    return primary.model_copy(
        update={
            "authors": a.authors or b.authors,
            "abstract": a.abstract or b.abstract,
            "publication_date": a.publication_date or b.publication_date,
            "url": primary.url or a.url or b.url,
            "sources": list(dict.fromkeys(a.sources + b.sources)),
            "paper_type": a.paper_type or b.paper_type,
            "citation_count": max(
                (
                    count
                    for count in (a.citation_count, b.citation_count)
                    if count is not None
                ),
                default=None,
            ),
            "citation_links": list(citations.values())[:20],
        }
    )


def _matches_filters(paper: DiscoveryPaper, query: DiscoverySearchRequest) -> bool:
    if query.year_from is not None or query.year_to is not None:
        if not paper.publication_date:
            return False
        year = paper.publication_date.year
        if not (query.year_from or 1) <= year <= (query.year_to or 9999):
            return False
    return query.publication_type is None or paper.paper_type == query.publication_type


class DiscoveryGateway:
    def __init__(
        self,
        providers: dict[DiscoverySource, DiscoveryProvider],
        cache: SearchCache | None = None,
        timeout: float = 12,
    ):
        self._providers = providers
        self._cache = cache or SearchCache()
        self._timeout = timeout
        self._search_locks = [asyncio.Lock() for _ in range(64)]

    async def close(self) -> None:
        await asyncio.gather(
            *(provider.close() for provider in self._providers.values()),
            self._cache.close(),
        )

    async def _deadline(self, source: DiscoverySource, call: Awaitable[T]) -> T:
        try:
            return await asyncio.wait_for(call, timeout=self._timeout)
        except TimeoutError:
            raise ProviderUnavailable(source) from None

    async def search(self, query: DiscoverySearchRequest) -> DiscoverySearchResponse:
        filters = query.model_dump(exclude={"limit", "offset"}, mode="json")
        filters["sources"] = sorted(query.sources)
        digest = hashlib.sha256(
            json.dumps(filters, sort_keys=True).encode()
        ).hexdigest()
        key = f"researchnest:discovery:search:v1:{digest}"
        snapshot = await self._cache.get(key)
        if snapshot is None:
            async with self._search_locks[
                int(digest[:2], 16) % len(self._search_locks)
            ]:
                snapshot = await self._cache.get(key)
                if snapshot is None:
                    snapshot = await self._search_providers(
                        query, sorted(query.sources)
                    )
                    await self._cache.put(key, snapshot)
        return DiscoverySearchResponse(
            items=snapshot.items[query.offset : query.offset + query.limit],
            total=len(snapshot.items),
            sources=snapshot.sources,
            warnings=snapshot.warnings,
            limit=query.limit,
            offset=query.offset,
        )

    async def _search_providers(
        self, query: DiscoverySearchRequest, sources: list[DiscoverySource]
    ) -> SearchSnapshot:
        async def search_provider(
            source: DiscoverySource,
        ) -> list[ProviderPaper] | None:
            provider = self._providers.get(source)
            if provider is None:
                return None
            try:
                return await self._deadline(
                    source,
                    provider.search(
                        query.q,
                        limit=PROVIDER_WINDOW,
                        year_from=query.year_from,
                        year_to=query.year_to,
                        field=query.field,
                    ),
                )
            except ProviderUnavailable:
                return None

        results = await asyncio.gather(*(search_provider(source) for source in sources))
        items = []
        successful = []
        warnings = []
        for source, batch in zip(sources, results, strict=True):
            if batch is None:
                warnings.append(source)
            else:
                successful.append(source)
                items.append(batch[:PROVIDER_WINDOW])
        if not successful:
            raise ProviderUnavailable("academic discovery")

        # Interleave provider rankings before merging duplicate records.
        merged: list[DiscoveryPaper] = []
        for rank in range(max(map(len, items), default=0)):
            for batch in items:
                if rank >= len(batch) or not (paper := _normalize(batch[rank])):
                    continue
                if not _matches_filters(paper, query):
                    continue
                exact_doi = (
                    next(
                        (i for i, prior in enumerate(merged) if prior.doi == paper.doi),
                        None,
                    )
                    if paper.doi
                    else None
                )
                duplicate = (
                    exact_doi
                    if exact_doi is not None
                    else next(
                        (
                            i
                            for i, prior in enumerate(merged)
                            if _same_paper(prior, paper)
                        ),
                        None,
                    )
                )
                if duplicate is None:
                    merged.append(paper)
                else:
                    merged[duplicate] = _merge(merged[duplicate], paper)
        if query.sort == "date":
            merged.sort(
                key=lambda item: item.publication_date or date.min, reverse=True
            )
        return SearchSnapshot(items=merged, sources=successful, warnings=warnings)

    async def lookup_doi(self, value: str) -> DiscoveryPaper:
        doi = normalize_doi(value)
        if not doi:
            raise InvalidPaperReference("Invalid DOI.")

        async def lookup(source: DiscoverySource, provider: DiscoveryProvider):
            try:
                return await self._deadline(source, provider.get_by_doi(doi))
            except ProviderUnavailable as error:
                return error

        # Crossref goes first so its record remains the primary DOI reference.
        ordered = sorted(self._providers, key=lambda item: (item != "crossref", item))
        responses = await asyncio.gather(
            *(lookup(source, self._providers[source]) for source in ordered)
        )
        matches = []
        for response in responses:
            if isinstance(response, ProviderPaper):
                paper = _normalize(response)
                if paper is not None and paper.doi == doi:
                    matches.append(paper)
        if matches:
            primary = matches[0]
            for paper in matches[1:]:
                primary = _merge(primary, paper)
            return primary
        if any(isinstance(item, ProviderUnavailable) for item in responses):
            raise ProviderUnavailable("DOI lookup")
        raise PaperNotFound("Paper not found.")

    async def verify_reference(self, reference: SaveToLibraryRequest) -> DiscoveryPaper:
        doi = normalize_doi(reference.doi)
        if reference.doi and not doi:
            raise InvalidPaperReference("Invalid DOI.")
        provider = self._providers.get(reference.source)
        if provider is None:
            raise ProviderUnavailable(reference.source)
        if reference.external_id:
            external_id = reference.external_id
            if not external_id.isprintable() or any(
                part in {".", ".."} for part in external_id.split("/")
            ):
                raise InvalidPaperReference("Invalid provider ID.")
            record = await self._deadline(
                reference.source, provider.get_by_id(external_id)
            )
        else:
            record = await self._deadline(reference.source, provider.get_by_doi(doi))
        paper = (
            _normalize(record) if record and record.source == reference.source else None
        )
        if not paper:
            raise PaperNotFound("Paper not found.")
        if doi and doi != paper.doi:
            raise InvalidPaperReference("DOI does not match the provider record.")
        if not (paper.external_id or paper.doi):
            raise PaperNotFound("Paper has no stable provider identifier.")
        return paper
