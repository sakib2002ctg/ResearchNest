import httpx
from sqlalchemy import select

from app.models.paper import PaperSource
from app.modules.discovery.gateway import DiscoveryGateway
from app.modules.discovery.library import _provider_metadata, save_to_library
from app.modules.discovery.providers import SemanticScholarProvider
from app.modules.discovery.router import get_discovery_gateway
from app.modules.discovery.schemas import CitationLink, DiscoveryPaper
from tests.modules.ai.test_assistant import authenticate

SAVE = "/api/v1/discovery/save-to-library"
GRAPH = "/api/v1/analytics/knowledge-graph"


def test_verified_provider_save_persists_updates_and_preserves_graph_citations(
    client, db, access_token, another_access_token
):
    records = {
        "S1": {
            "paperId": "S1",
            "title": "Plant ecology",
            "externalIds": {"DOI": "10.1234/ecology"},
            "citations": [
                {
                    "title": "Plant evolution",
                    "externalIds": {"DOI": "10.1234/evolution"},
                },
                {
                    "title": "Private library target",
                    "externalIds": {"DOI": "10.1234/private"},
                },
            ],
            "notes": "Must not be copied as global metadata",
            "user_id": 9999,
        },
        "S2": {
            "paperId": "S2",
            "title": "Plant evolution",
            "externalIds": {"DOI": "10.1234/evolution"},
        },
        "S3": {
            "paperId": "S3",
            "title": "Private library target",
            "externalIds": {"DOI": "10.1234/private"},
        },
    }
    calls = []

    def upstream(request):
        calls.append(request)
        assert "citations.externalIds" in request.url.params["fields"].split(",")
        return httpx.Response(200, json=records[request.url.path.rsplit("/", 1)[-1]])

    gateway = DiscoveryGateway(
        {
            "semantic_scholar": SemanticScholarProvider(
                transport=httpx.MockTransport(upstream),
                max_retries=0,
                min_interval=0,
            )
        }
    )
    client.app.dependency_overrides[get_discovery_gateway] = lambda: gateway
    try:
        authenticate(client, another_access_token)
        assert (
            client.post(
                SAVE, json={"source": "semantic_scholar", "external_id": "S3"}
            ).status_code
            == 200
        )
        authenticate(client, access_token)
        target = client.post(
            SAVE, json={"source": "semantic_scholar", "external_id": "S2"}
        ).json()
        result = client.post(
            SAVE, json={"source": "semantic_scholar", "external_id": "S1"}
        )
        assert result.status_code == 200, result.text
        source = result.json()
        graph_response = client.get(GRAPH)
        assert graph_response.status_code == 200, graph_response.text
        edges = [
            e for e in graph_response.json()["edges"] if e["type"] == "cites_or_related"
        ]
        assert len(edges) == 1
        assert edges[0]["source"] == f"paper:{source['user_paper_id']}"
        assert edges[0]["target"] == f"paper:{target['user_paper_id']}"
        assert "Private library target" not in graph_response.text
        assert (
            "incoming citations" in graph_response.json()["legend"]["cites_or_related"]
        )
        db.expire_all()
        record = db.scalar(select(PaperSource).where(PaperSource.external_id == "S1"))
        assert record.metadata_json["citation_direction"] == "incoming_cited_by"
        assert len(record.metadata_json["citation_links"]) == 2
        assert not {"notes", "user_id", "token", "prompt"} & record.metadata_json.keys()

        records["S1"]["title"] = "Plant ecology metadata refreshed"
        records["S1"]["citations"][0]["title"] = "Verified incoming link refreshed"
        assert (
            client.post(
                SAVE, json={"source": "semantic_scholar", "external_id": "S1"}
            ).json()["already_saved"]
            is True
        )
        db.expire_all()
        db.refresh(record)
        refreshed_links = record.metadata_json["citation_links"]
        assert record.metadata_json["title"] == "Plant ecology metadata refreshed"
        assert refreshed_links[0]["title"] == "Verified incoming link refreshed"

        records["S1"].pop("citations")
        assert (
            client.post(
                SAVE, json={"source": "semantic_scholar", "external_id": "S1"}
            ).status_code
            == 200
        )
        db.expire_all()
        db.refresh(record)
        assert record.metadata_json["citation_links"] == refreshed_links
        assert (
            len(
                [
                    e
                    for e in client.get(GRAPH).json()["edges"]
                    if e["type"] == "cites_or_related"
                ]
            )
            == 1
        )
        before = len(calls)
        forged = client.post(
            SAVE,
            json={
                "source": "semantic_scholar",
                "external_id": "S1",
                "citation_links": [{"doi": "10.1234/forged"}],
            },
        )
        assert forged.status_code == 422 and len(calls) == before
    finally:
        client.app.dependency_overrides.pop(get_discovery_gateway, None)
        client.portal.call(gateway.close)


def test_metadata_snapshot_allowlist_bounds_and_doi_only_source(db, test_user):
    paper = DiscoveryPaper(
        title="Provider title",
        authors=["Author"],
        doi="10.1234/doi-only",
        source="crossref",
        citation_links=[
            CitationLink(
                title="Recorded link",
                doi="10.1234/target",
                source="crossref",
            )
        ],
    )
    result = save_to_library(db, test_user.id, paper)
    row = db.scalar(select(PaperSource).where(PaperSource.paper_id == result.paper_id))
    assert row.external_id == "10.1234/doi-only"
    assert row.metadata_json["citation_links"][0]["doi"] == "10.1234/target"
    no_links = paper.model_copy(update={"citation_links": []})
    old = {
        "private_notes": "Excluded",
        "citation_links": [
            "bad",
            {"title": "Invalid source", "source": "unknown"},
            {
                "title": "Valid old record",
                "source": "crossref",
                "doi": "10.1234/old",
                "user_id": 99,
            },
            {"title": "Duplicate", "source": "crossref", "doi": "10.1234/old"},
        ],
    }
    snapshot = _provider_metadata(no_links, old)
    assert snapshot["citation_links"] == [
        {
            "title": "Valid old record",
            "source": "crossref",
            "doi": "10.1234/old",
            "url": None,
        }
    ]
    assert "private_notes" not in snapshot
    assert (
        _provider_metadata(no_links, {"venue": "  Public\x00 journal  "})["venue"]
        == "Public journal"
    )
    assert len(_provider_metadata(no_links, {"venue": "V" * 600})["venue"]) == 500
    assert "venue" not in _provider_metadata(no_links, {"venue": ["invalid"]})
    assert (
        _provider_metadata(no_links, {"citation_links": "bad"})["citation_links"] == []
    )
