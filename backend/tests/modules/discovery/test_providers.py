from __future__ import annotations

import asyncio
from collections import Counter
from functools import wraps
from urllib.parse import parse_qs

import httpx
import pytest

from app.modules.discovery.providers import (
    ArxivProvider,
    CrossrefProvider,
    OpenAlexProvider,
    ProviderPaper,
    ProviderUnavailable,
    PubMedProvider,
    SemanticScholarProvider,
)


@pytest.fixture
def sleeps():
    values: list[float] = []

    async def record(seconds: float) -> None:
        values.append(seconds)

    return values, record


def run_async(test):
    @wraps(test)
    def wrapped(*args, **kwargs):
        asyncio.run(test(*args, **kwargs))

    return wrapped


def json_response(
    request: httpx.Request, payload: object, status: int = 200
) -> httpx.Response:
    return httpx.Response(
        status,
        headers={"Content-Type": "application/json"},
        json=payload,
        request=request,
    )


@run_async
async def test_arxiv_search_parses_atom_and_maps_author_title_abstract_id():
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>https://arxiv.org/abs/2401.01234v2</id>
        <published>2024-01-03T00:00:00Z</published>
        <title>  Safe   Discovery  </title>
        <summary>Structured academic search.</summary>
        <author><name>Ada Lovelace</name></author>
        <category term="cs.IR" />
        <link rel="alternate" href="https://arxiv.org/abs/2401.01234" />
      </entry>
    </feed>"""

    def handler(request: httpx.Request) -> httpx.Response:
        if "id_list" in request.url.params:
            assert request.url.params["id_list"] == "2401.01234"
        else:
            assert request.url.params["search_query"] == "ti:discovery"
            assert request.url.params["max_results"] == "5"
        return httpx.Response(200, content=xml, request=request)

    provider = ArxivProvider(
        transport=httpx.MockTransport(handler),
        min_interval=0,
        sleep=lambda _: asyncio.sleep(0),
    )
    result = await provider.search("discovery", limit=5, field="title")
    resolved = await provider.get_by_id("2401.01234")
    await provider.close()
    assert result == [
        ProviderPaper(
            title="Safe Discovery",
            authors=["Ada Lovelace"],
            abstract="Structured academic search.",
            doi=None,
            publication_date="2024-01-03",
            url="https://arxiv.org/abs/2401.01234",
            source="arxiv",
            external_id="2401.01234v2",
            paper_type="preprint:cs.IR",
            citation_count=None,
        )
    ]
    assert resolved == result[0]


@run_async
async def test_arxiv_query_failures_are_safe_and_field_filters_are_explicit():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, request=request)

    provider = ArxivProvider(
        transport=httpx.MockTransport(handler),
        max_retries=0,
        min_interval=0,
        sleep=lambda _: asyncio.sleep(0),
    )
    with pytest.raises(ProviderUnavailable) as error:
        await provider.search("private query")
    await provider.close()
    assert str(error.value) == "The arxiv provider is temporarily unavailable."
    assert "private query" not in str(error.value)
    assert await provider.search("  ") == []


@run_async
async def test_http_client_retries_rate_limit_and_uses_capped_retry_after(sleeps):
    delays, sleep = sleeps
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "30"}, request=request)
        return json_response(request, {"results": []})

    provider = OpenAlexProvider(
        transport=httpx.MockTransport(handler),
        max_retries=2,
        min_interval=0,
        max_retry_after=0.25,
        sleep=sleep,
    )
    result = await provider.search("retrieval", limit=2)
    await provider.close()
    assert result == []
    assert calls == 2
    assert delays == [0.25]


@run_async
async def test_http_client_retries_transient_transport_failures():
    calls = 0
    delays: list[float] = []

    async def sleep(value: float) -> None:
        delays.append(value)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("secret query details", request=request)
        return json_response(request, {"message": {"items": []}})

    provider = CrossrefProvider(
        transport=httpx.MockTransport(handler),
        max_retries=2,
        min_interval=0,
        sleep=sleep,
    )
    assert await provider.search("metadata") == []
    await provider.close()
    assert calls == 2
    assert len(delays) == 1 and 0 <= delays[0] <= 1.5


@run_async
async def test_openalex_maps_authorship_inverted_abstract_and_doi():
    work = {
        "id": "https://openalex.org/W1",
        "title": "Research systems",
        "doi": "https://doi.org/10.1000/ABC",
        "publication_date": "2022-09-01",
        "authorships": [{"author": {"display_name": "Grace Hopper"}}],
        "abstract_inverted_index": {"search": [2], "safe": [0], "is": [1]},
        "primary_location": {"landing_page_url": "https://example.org/paper"},
        "type": "article",
        "cited_by_count": 12,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer openalex-test-key"
        if request.url.path.endswith("/works"):
            return json_response(request, {"results": [work]})
        assert "/works/" in request.url.path
        return json_response(request, work)

    provider = OpenAlexProvider(
        api_key="openalex-test-key",
        transport=httpx.MockTransport(handler),
        min_interval=0,
        sleep=lambda _: asyncio.sleep(0),
    )
    results = await provider.search("systems", year_from=2020, year_to=2023)
    resolved = await provider.get_by_doi("10.1000/ABC")
    by_id = await provider.get_by_id("https://openalex.org/W1")
    await provider.close()
    assert results[0].abstract == "safe is search"
    assert results[0].authors == ["Grace Hopper"]
    assert results[0].doi == "10.1000/abc"
    assert results[0].citation_count == 12
    assert resolved is not None and resolved.external_id == "https://openalex.org/W1"
    assert by_id == resolved


@run_async
async def test_crossref_maps_metadata_and_doi_lookup():
    item = {
        "title": ["Cross-provider paper"],
        "DOI": "10.1000/crossref",
        "author": [{"given": "Katherine", "family": "Johnson"}],
        "published": {"date-parts": [[2021, 5, 2]]},
        "URL": "https://doi.org/10.1000/crossref",
        "type": "journal-article",
        "is-referenced-by-count": 9,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert any(
            name.startswith("query") for name in request.url.params
        ) or request.url.path.endswith("/crossref")
        return json_response(
            request,
            (
                {"message": {"items": [item]}}
                if request.url.path.endswith("/works")
                else {"message": item}
            ),
        )

    provider = CrossrefProvider(
        transport=httpx.MockTransport(handler),
        min_interval=0,
        sleep=lambda _: asyncio.sleep(0),
    )
    result = (await provider.search("cross-provider", field="title"))[0]
    resolved = await provider.get_by_doi("https://doi.org/10.1000/crossref")
    by_id = await provider.get_by_id("10.1000/crossref")
    await provider.close()
    assert result.title == "Cross-provider paper"
    assert result.authors == ["Katherine Johnson"]
    assert result.publication_date == "2021-05-02"
    assert result.citation_count == 9
    assert result.doi == "10.1000/crossref"
    assert resolved == by_id == result


@run_async
async def test_semantic_scholar_optional_key_recommendations_and_citations():
    calls: Counter[str] = Counter()
    paper = {
        "paperId": "S1",
        "title": "Graph paper",
        "abstract": "A useful abstract",
        "authors": [{"name": "Lin"}],
        "year": 2019,
        "externalIds": {"DOI": "10.1000/graph"},
        "citationCount": 31,
        "publicationTypes": ["JournalArticle"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        calls[request.url.path] += 1
        if request.url.path.endswith("/search"):
            assert request.headers["x-api-key"] == "test-key"
            return json_response(request, {"data": [paper]})
        if "/recommendations/" in request.url.path:
            return json_response(request, {"recommendedPapers": [paper]})
        if request.url.path.endswith("/citations"):
            assert "title" in request.url.params["fields"].split(",")
            return json_response(request, {"data": [{"citingPaper": paper}]})
        if "DOI:" in request.url.path:
            assert "citations.externalIds" in request.url.params["fields"].split(",")
            return json_response(request, {**paper, "citations": [paper]})
        return json_response(request, paper)

    provider = SemanticScholarProvider(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        min_interval=0,
        sleep=lambda _: asyncio.sleep(0),
    )
    results = await provider.search("graphs", year_from=2018, year_to=2020)
    recommendations = await provider.recommendations("S1", limit=2)
    citations = await provider.citations("S1", limit=3)
    links = await provider.citation_links("S1", limit=3)
    by_id = await provider.get_by_id("S1")
    by_doi = await provider.get_by_doi("https://doi.org/10.1000/graph")
    await provider.close()
    assert results[0].doi == "10.1000/graph"
    assert results[0].citation_count == 31
    assert len(recommendations) == len(citations) == 1
    assert by_id == results[0]
    assert links[0].doi == "10.1000/graph"
    assert by_doi is not None and by_doi.citation_links == links
    assert sum(calls.values()) == 6


@run_async
async def test_pubmed_esearch_efetch_parse_and_doi_resolution():
    xml = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation>
      <PMID>12345</PMID><Article><ArticleTitle>Biomedical finding</ArticleTitle>
      <AuthorList>
        <Author><LastName>Curie</LastName><Initials>M</Initials></Author>
      </AuthorList>
      <Abstract><AbstractText>Important result.</AbstractText></Abstract>
      <Journal>
        <Title>Medical Journal</Title>
        <JournalIssue><PubDate><Year>2020</Year></PubDate></JournalIssue>
      </Journal>
      <PublicationTypeList>
        <PublicationType>Clinical Trial</PublicationType>
      </PublicationTypeList>
      <ELocationID EIdType="doi">10.1000/pm</ELocationID>
      </Article></MedlineCitation>
      <PubmedData>
        <ArticleIdList><ArticleId IdType="doi">10.1000/pm</ArticleId></ArticleIdList>
      </PubmedData>
      </PubmedArticle></PubmedArticleSet>"""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "optional-key" not in str(request.url)
        form = parse_qs(request.content.decode())
        assert form["api_key"] == ["optional-key"]
        if request.url.path.endswith("esearch.fcgi"):
            assert form["db"] == ["pubmed"]
            return json_response(request, {"esearchresult": {"idlist": ["12345"]}})
        assert form["id"] == ["12345"]
        return httpx.Response(200, content=xml, request=request)

    provider = PubMedProvider(
        email="research@example.org",
        api_key="optional-key",
        transport=httpx.MockTransport(handler),
        min_interval=0,
        sleep=lambda _: asyncio.sleep(0),
    )
    results = await provider.search("biomedical", field="title")
    resolved = await provider.get_by_doi("10.1000/pm")
    by_id = await provider.get_by_id("12345")
    await provider.close()
    assert results[0].title == "Biomedical finding"
    assert results[0].authors == ["Curie M"]
    assert results[0].abstract == "Important result."
    assert results[0].source == "pubmed"
    assert results[0].publication_date == "2020"
    assert results[0].external_id == "12345"
    assert results[0].doi == "10.1000/pm"
    assert results[0].paper_type == "Clinical Trial"
    assert resolved == by_id == results[0]


@run_async
async def test_pagination_is_clamped_and_all_provider_types_filter_normalized_results():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return json_response(
            request,
            {
                "message": {
                    "items": [
                        {
                            "title": ["Review from 2020"],
                            "author": [],
                            "published": {"date-parts": [[2020]]},
                            "type": "review",
                        },
                        {
                            "title": ["Old article"],
                            "author": [],
                            "published": {"date-parts": [[2000]]},
                            "type": "journal-article",
                        },
                    ]
                }
            },
        )

    provider = CrossrefProvider(
        transport=httpx.MockTransport(handler),
        min_interval=0,
        sleep=lambda _: asyncio.sleep(0),
    )
    papers = await provider.search(
        "medicine",
        limit=1000,
        offset=-5,
        year_from=2010,
        year_to=2022,
        paper_type="review",
    )
    await provider.close()
    assert len(papers) == 1
    assert papers[0].title == "Review from 2020"
    assert calls[0].url.params["rows"] == "50"
    assert calls[0].url.params["offset"] == "0"


@run_async
async def test_openalex_offset_can_span_page_boundaries():
    pages = []

    def handler(request: httpx.Request) -> httpx.Response:
        size = int(request.url.params["per_page"])
        page = int(request.url.params["page"])
        pages.append(page)
        start = (page - 1) * size
        return json_response(
            request,
            {
                "results": [
                    {"title": str(index)} for index in range(start, start + size)
                ]
            },
        )

    async with OpenAlexProvider(
        transport=httpx.MockTransport(handler), min_interval=0
    ) as provider:
        papers = await provider.search("metadata", limit=3, offset=98)

    assert [paper.title for paper in papers] == ["98", "99", "100"]
    assert pages == [1, 2]


@run_async
async def test_crossref_distinguishes_missing_records_and_broken_payloads():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/absent"):
            return httpx.Response(404, request=request)
        return httpx.Response(
            200, content=b"untrusted provider response", request=request
        )

    async with CrossrefProvider(
        transport=httpx.MockTransport(handler), min_interval=0
    ) as provider:
        assert await provider.get_by_doi("10.1000/absent") is None
        with pytest.raises(ProviderUnavailable) as error:
            await provider.search("query")

    assert str(error.value) == "The crossref provider is temporarily unavailable."
