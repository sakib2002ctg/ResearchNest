from urllib.parse import quote

import httpx
import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.database.database import Base
from app.database.discovery_database import _async_database_url
from app.models.paper import Paper, UserPaper
from app.modules.discovery.gateway import DiscoveryGateway
from app.modules.discovery.providers import CrossrefProvider, OpenAlexProvider
from app.modules.discovery.router import get_discovery_gateway

DISCOVERY = "/api/v1/discovery"
PAPERS = "/api/v1/papers"
EXPORT = "/api/v1/users/me/export"
DOI = "10.1234/climate/report"
TITLE = "Climate Adaptation in Coastal Cities"
MISSING_DOI = "10.1234/missing"
REFERENCE = {"source": "crossref", "doi": DOI}


@pytest.fixture
def db(tmp_path, monkeypatch):
    # Both session factories use the same isolated database file.
    url = URL.create("sqlite", database=str(tmp_path / "discovery.sqlite"))
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    monkeypatch.setattr("app.main.settings.DATABASE_URL", str(url))
    monkeypatch.setattr("app.main.engine", engine)
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def test_async_database_url_preserves_configured_postgresql_credentials():
    url = _async_database_url("postgresql+psycopg2://reader:s%40cret@localhost:5432/db")
    assert url.drivername == "postgresql+asyncpg"
    assert url.username == "reader"
    assert url.password == "s@cret"
    assert url.database == "db"


@pytest.fixture
def upstream(client):
    crossref_paper = {
        "DOI": DOI,
        "title": [TITLE],
        "author": [{"given": "Ada", "family": "Lovelace"}],
        "abstract": "<jats:p>Field data from coastal cities.</jats:p>",
        "published": {"date-parts": [[2022, 3, 4]]},
        "URL": f"https://doi.org/{DOI}",
        "type": "journal-article",
        "is-referenced-by-count": 6,
    }
    environmental_policy = {
        **crossref_paper,
        "DOI": "10.1234/coastal-policy",
        "title": ["Coastal policy: A review"],
        "published": {"date-parts": [[2021, 1, 1]]},
        "type": "review",
    }
    openalex_duplicate = {
        "id": "https://openalex.org/W101",
        "doi": f"https://doi.org/{DOI.upper()}",
        "title": TITLE,
        "publication_date": "2022-03-04",
        "authorships": [{"author": {"display_name": "Ada Lovelace"}}],
        "type": "article",
        "cited_by_count": 25,
    }
    new_paper = {
        **openalex_duplicate,
        "id": "https://openalex.org/W102",
        "doi": None,
        "title": "Wetland Restoration",
        "publication_date": "2024-02-06",
    }
    policy_duplicate = {
        **openalex_duplicate,
        "id": "https://openalex.org/W103",
        "doi": None,
        "title": "Coastal Policy – A Review",
        "publication_date": "2021-01-01",
        "type": "review",
    }
    old_paper = {
        **openalex_duplicate,
        "id": "https://openalex.org/W104",
        "doi": None,
        "title": "Historic Sediment Records",
        "publication_date": "2001-08-08",
    }
    requests = []
    unavailable = set()

    def mock_provider(request):
        requests.append(request)
        host = request.url.host
        path = request.url.path
        if host in unavailable:
            return httpx.Response(503, text="Internal mock provider diagnostics")
        if host == "api.crossref.org":
            if path == "/works":
                return httpx.Response(
                    200,
                    json={"message": {"items": [crossref_paper, environmental_policy]}},
                )
            if path == f"/works/{DOI}":
                return httpx.Response(200, json={"message": crossref_paper})
        if host == "api.openalex.org":
            if path == "/works":
                return httpx.Response(
                    200,
                    json={
                        "results": [
                            openalex_duplicate,
                            new_paper,
                            policy_duplicate,
                            old_paper,
                        ]
                    },
                )
            if path in (f"/works/https://doi.org/{DOI}", "/works/W101"):
                return httpx.Response(200, json=openalex_duplicate)
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_provider)
    gateway = DiscoveryGateway(
        {
            "crossref": CrossrefProvider(
                transport=transport, max_retries=0, min_interval=0
            ),
            "openalex": OpenAlexProvider(
                transport=transport, max_retries=0, min_interval=0
            ),
        }
    )

    def override_gateway():
        yield gateway

    client.app.dependency_overrides[get_discovery_gateway] = override_gateway
    try:
        yield requests, unavailable
    finally:
        client.app.dependency_overrides.pop(get_discovery_gateway, None)
        client.portal.call(gateway.close)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_search_deduplicates_and_pages_through_cached_results(client, upstream):
    requests, _ = upstream
    path = f"{DISCOVERY}/search"
    query = {"q": "coastal climate", "sources": ["crossref", "openalex"], "limit": 2}
    first = client.post(path, json=query)
    second = client.post(
        path, json={**query, "sources": list(reversed(query["sources"])), "offset": 2}
    )

    assert first.status_code == second.status_code == 200
    first_page = first.json()
    second_page = second.json()
    assert first_page["total"] == second_page["total"] == 4
    assert first_page["offset"] == 0
    assert second_page["offset"] == 2
    assert first_page["limit"] == second_page["limit"] == 2
    assert set(first_page["sources"]) == {"crossref", "openalex"}
    assert first_page["warnings"] == second_page["warnings"] == []

    results = first_page["items"] + second_page["items"]
    assert [paper["title"] for paper in results] == [
        TITLE,
        "Coastal policy: A review",
        "Wetland Restoration",
        "Historic Sediment Records",
    ]
    matched_doi, matched_title = results[:2]
    assert matched_doi["doi"] == DOI
    assert matched_doi["authors"] == ["Ada Lovelace"]
    assert matched_doi["abstract"] == "Field data from coastal cities."
    assert matched_doi["citation_count"] == 25
    assert (
        set(matched_doi["sources"])
        == set(matched_title["sources"])
        == {
            "crossref",
            "openalex",
        }
    )
    assert len(requests) == 2


def test_search_filters_by_source_year_type_and_sorts_by_date(client, upstream):
    requests, _ = upstream
    response = client.post(
        f"{DISCOVERY}/search",
        json={
            "q": "coastal climate",
            "sources": ["openalex"],
            "year_from": 2020,
            "year_to": 2024,
            "publication_type": "article",
            "sort": "date",
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 2
    assert result["sources"] == ["openalex"]
    assert [paper["title"] for paper in result["items"]] == [
        "Wetland Restoration",
        TITLE,
    ]
    assert len(requests) == 1
    assert requests[0].url.host == "api.openalex.org"


@pytest.mark.parametrize(
    "invalid_fields",
    [{"q": " "}, {"sources": []}, {"year_from": 2025, "year_to": 2020}, {"limit": 51}],
)
def test_invalid_search_does_not_contact_providers(client, upstream, invalid_fields):
    requests, _ = upstream
    response = client.post(
        f"{DISCOVERY}/search", json={"q": "coastal climate", **invalid_fields}
    )

    assert response.status_code == 422
    assert requests == []


def test_partial_provider_failure_keeps_results_and_reports_source(client, upstream):
    _, unavailable = upstream
    unavailable.add("api.openalex.org")
    response = client.post(
        f"{DISCOVERY}/search",
        json={"q": "coastal climate", "sources": ["openalex", "crossref"]},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert response.json()["sources"] == ["crossref"]
    assert response.json()["warnings"] == ["openalex"]


def test_all_provider_failures_return_service_unavailable(client, upstream):
    _, unavailable = upstream
    unavailable.update({"api.openalex.org", "api.crossref.org"})
    response = client.post(
        f"{DISCOVERY}/search",
        json={"q": "coastal climate", "sources": ["openalex", "crossref"]},
    )

    assert response.status_code == 503
    assert "Internal mock provider diagnostics" not in response.text


def test_doi_lookup_accepts_encoded_slashes_and_merges_metadata(client, upstream):
    response = client.get(f"{DISCOVERY}/doi/{quote(DOI.upper(), safe='')}")

    assert response.status_code == 200
    result = response.json()
    assert result["doi"] == DOI
    assert result["source"] == "crossref"
    assert set(result["sources"]) == {"crossref", "openalex"}
    assert result["citation_count"] == 25


@pytest.mark.parametrize(("value", "status"), [("not-a-doi", 422), (MISSING_DOI, 404)])
def test_doi_lookup_rejects_invalid_or_missing_records(client, upstream, value, status):
    response = client.get(f"{DISCOVERY}/doi/{quote(value, safe='')}")

    assert response.status_code == status


def test_save_requires_authentication_before_provider_lookup(client, upstream):
    requests, _ = upstream
    response = client.post(f"{DISCOVERY}/save-to-library", json=REFERENCE)

    assert response.status_code == 401
    assert requests == []


@pytest.mark.parametrize(
    ("payload", "status"),
    [
        ({**REFERENCE, "title": "Unverified title"}, 422),
        ({**REFERENCE, "user_id": 2}, 422),
        ({"source": "crossref"}, 422),
        ({"source": "crossref", "external_id": DOI, "doi": MISSING_DOI}, 422),
        ({"source": "crossref", "doi": MISSING_DOI}, 404),
    ],
)
def test_cannot_save_forged_metadata_or_unverified_references(
    client, db, access_token, upstream, payload, status
):
    response = client.post(
        f"{DISCOVERY}/save-to-library", json=payload, headers=auth(access_token)
    )

    assert response.status_code == status
    assert db.scalar(select(func.count()).select_from(Paper)) == 0
    assert db.scalar(select(func.count()).select_from(UserPaper)) == 0


def test_saved_papers_share_catalog_metadata_but_library_membership_is_private(
    client, db, access_token, another_access_token, upstream
):
    path = f"{DISCOVERY}/save-to-library"
    owner = auth(access_token)
    other = auth(another_access_token)
    first = client.post(path, json=REFERENCE, headers=owner)
    assert first.status_code == 200
    saved = first.json()
    assert saved["saved"] and not saved["already_saved"]

    repeated = client.post(path, json=REFERENCE, headers=owner)
    assert repeated.status_code == 200
    assert repeated.json() == {**saved, "already_saved": True}

    owner_list = client.get(f"{PAPERS}/", headers=owner)
    assert owner_list.status_code == 200
    assert owner_list.json()["total"] == 1
    private_paper = owner_list.json()["items"][0]
    assert private_paper["title"] == TITLE
    assert private_paper["authors"] == "Ada Lovelace"
    paper_path = f"{PAPERS}/{private_paper['id']}"
    assert client.get(paper_path, headers=owner).status_code == 200
    assert client.get(paper_path, headers=other).status_code == 404
    assert client.get(f"{PAPERS}/", headers=other).json()["total"] == 0
    assert client.get(EXPORT, headers=other).json()["papers"] == []
    assert [p["id"] for p in client.get(EXPORT, headers=owner).json()["papers"]] == [
        private_paper["id"]
    ]

    other_save = client.post(
        path,
        json={"source": "openalex", "external_id": "W101"},
        headers=other,
    )
    assert other_save.status_code == 200
    assert other_save.json()["paper_id"] == saved["paper_id"]
    assert other_save.json()["user_paper_id"] != saved["user_paper_id"]
    assert not other_save.json()["already_saved"]
    assert client.get(paper_path, headers=other).status_code == 404
    assert db.scalar(select(func.count()).select_from(Paper)) == 1
    assert db.scalar(select(func.count()).select_from(UserPaper)) == 2
