from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Literal, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel, ConfigDict, Field


class ProviderUnavailable(RuntimeError):
    """A safe, provider-specific failure with no request or credential details."""

    def __init__(self, source: str) -> None:
        super().__init__(f"The {source} provider is temporarily unavailable.")
        self.source = source


ProviderSource = Literal["arxiv", "openalex", "crossref", "semantic_scholar", "pubmed"]


class ProviderCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    url: str | None = None
    doi: str | None = None
    source: ProviderSource


class ProviderPaper(BaseModel):
    """Provider-normalized scholarly work metadata."""

    model_config = ConfigDict(extra="forbid")

    title: str
    authors: list[str] = Field(default_factory=list)
    abstract: str | None = None
    doi: str | None = None
    publication_date: str | None = None
    url: str | None = None
    source: ProviderSource
    external_id: str | None = None
    paper_type: str | None = None
    citation_count: int | None = Field(default=None, ge=0)
    citation_links: list[ProviderCitation] = Field(default_factory=list)


@runtime_checkable
class DiscoveryProvider(Protocol):
    source: str

    async def search(
        self,
        query: str,
        limit: int = 20,
        offset: int = 0,
        year_from: int | None = None,
        year_to: int | None = None,
        paper_type: str | None = None,
        field: Literal["all", "title", "author", "id"] = "all",
    ) -> list[ProviderPaper]: ...

    async def get_by_doi(self, doi: str) -> ProviderPaper | None: ...

    async def get_by_id(self, external_id: str) -> ProviderPaper | None: ...

    async def close(self) -> None: ...


Sleep = Callable[[float], Awaitable[None]]


class AsyncProvider:
    """Shared bounded HTTP, concurrency, retry, and result-filtering safeguards."""

    source = "academic"
    min_request_interval = 0.2

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
        max_retries: int = 2,
        concurrency: int = 1,
        min_interval: float | None = None,
        max_retry_after: float = 2.0,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._owns_client = client is None
        timeout = min(30.0, max(0.1, timeout))
        self._timeout = httpx.Timeout(timeout, connect=min(timeout, 3.0))
        self._client = client or httpx.AsyncClient(
            timeout=self._timeout,
            transport=transport,
            follow_redirects=False,
            headers={"User-Agent": "ResearchNest/2.0 (academic discovery)"},
        )
        self._max_retries = max(0, min(max_retries, 4))
        interval = self.min_request_interval if min_interval is None else min_interval
        self._min_interval = max(0.0, min(interval, 5.0))
        self._max_retry_after = max(0.0, min(max_retry_after, 5.0))
        self._sleep = sleep
        self._semaphore = asyncio.Semaphore(max(1, min(concurrency, 8)))
        self._rate_lock = asyncio.Lock()
        self._next_request_at = 0.0

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncProvider:
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()

    @staticmethod
    def _retry_after(value: str | None, cap: float) -> float | None:
        if not value:
            return None
        try:
            return min(cap, max(0.0, float(value)))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=UTC)
                return min(
                    cap, max(0.0, (retry_at - datetime.now(UTC)).total_seconds())
                )
            except (TypeError, ValueError, OverflowError):
                return None

    async def _wait_for_rate_slot(self) -> None:
        async with self._rate_lock:
            now = time.monotonic()
            wait = max(0.0, self._next_request_at - now)
            self._next_request_at = max(now, self._next_request_at) + self._min_interval
        if wait:
            await self._sleep(wait)

    async def _get(
        self,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        allow_not_found: bool = False,
    ) -> httpx.Response:
        return await self._request(
            "GET", url, params=params, headers=headers, allow_not_found=allow_not_found
        )

    async def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, str | int] | None = None,
        data: dict[str, str | int] | None = None,
        headers: dict[str, str] | None = None,
        allow_not_found: bool = False,
    ) -> httpx.Response:
        async with self._semaphore:
            for attempt in range(self._max_retries + 1):
                await self._wait_for_rate_slot()
                try:
                    response = await self._client.request(
                        method,
                        url,
                        params=params,
                        data=data,
                        headers=headers,
                        timeout=self._timeout,
                        follow_redirects=False,
                    )
                except (httpx.TimeoutException, httpx.TransportError):
                    if attempt >= self._max_retries:
                        raise ProviderUnavailable(self.source) from None
                    delay = min(1.5, 0.15 * (2**attempt) + random.uniform(0, 0.05))
                    await self._sleep(delay)
                    continue

                if response.status_code == 429 or response.status_code >= 500:
                    if attempt >= self._max_retries:
                        raise ProviderUnavailable(self.source)
                    retry_after = self._retry_after(
                        response.headers.get("Retry-After"), self._max_retry_after
                    )
                    delay = retry_after
                    if delay is None:
                        delay = min(1.5, 0.15 * (2**attempt) + random.uniform(0, 0.05))
                    await self._sleep(delay)
                    continue

                if allow_not_found and response.status_code == 404:
                    return response
                if not response.is_success:
                    raise ProviderUnavailable(self.source)
                return response

        raise ProviderUnavailable(self.source)

    def _json(self, response: httpx.Response) -> object:
        try:
            return response.json()
        except ValueError:
            raise ProviderUnavailable(self.source) from None

    @staticmethod
    def _records(value: object) -> list[dict]:
        return (
            [item for item in value if isinstance(item, dict)]
            if isinstance(value, list)
            else []
        )

    @staticmethod
    def validate_pagination(limit: int, offset: int) -> tuple[int, int]:
        return max(1, min(limit, 50)), max(0, min(offset, 100_000))

    @staticmethod
    def normalize_doi(doi: str) -> str:
        normalized = doi.strip().lower()
        for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix) :]
                break
        return normalized.strip().strip("/")

    @staticmethod
    def filter_results(
        papers: list[ProviderPaper],
        year_from: int | None,
        year_to: int | None,
        paper_type: str | None,
    ) -> list[ProviderPaper]:
        result: list[ProviderPaper] = []
        wanted_type = paper_type.strip().casefold() if paper_type else None
        for paper in papers:
            if year_from is not None or year_to is not None:
                try:
                    year = int((paper.publication_date or "")[:4])
                except ValueError:
                    continue
                if year_from is not None and year < year_from:
                    continue
                if year_to is not None and year > year_to:
                    continue
            if wanted_type and wanted_type not in (paper.paper_type or "").casefold():
                continue
            result.append(paper)
        return result
