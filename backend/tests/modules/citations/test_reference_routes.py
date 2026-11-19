from datetime import date
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, select

from app.models.audit_log import AuditLog
from app.models.paper import Author, Paper, PaperAuthor, PaperSource
from app.models.research_paper import ResearchPaper
from app.modules.discovery.gateway import PaperNotFound
from app.modules.discovery.providers import ProviderUnavailable
from app.modules.discovery.schemas import DiscoveryPaper
from tests.modules.ai.test_assistant import authenticate, indexed_paper

BASE = "/api/v1/citations"
MANUAL = {
    "title": "Research and Evidence",
    "authors": ["Ada Lovelace"],
    "year": 2026,
    "venue": "Research Journal",
    "doi": "10.1234/evidence",
    "cite_key": "lovelace2026evidence",
}


def create(client, **values):
    return client.post(BASE, json={**MANUAL, **values})


def test_manual_crud_dedup_metadata_warnings_and_safe_serialization(
    client, db, test_user, access_token
):
    authenticate(client, access_token)
    response = create(client)
    assert response.status_code == 201, response.text
    result = response.json()
    citation_id = result["id"]
    assert result["doi"] == "10.1234/evidence" and result["is_verified"] is False
    assert result["warnings"] and "identity_key" not in result
    assert response.headers["cache-control"] == "private, no-store"
    assert (
        create(
            client, doi="https://doi.org/10.1234/EVIDENCE", cite_key="different"
        ).json()["id"]
        == citation_id
    )
    assert (
        create(client, doi=None, title="  RESEARCH  AND EVIDENCE !!! ").json()["id"]
        == citation_id
    )
    assert len(client.get(BASE).json()) == 1
    assert client.get(BASE, params={"q": "Evidence"}).json()[0]["id"] == citation_id
    updated = client.put(
        f"{BASE}/{citation_id}", json={"venue": "Updated Journal", "volume": "2"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["venue"] == "Updated Journal"
    assert (
        client.put(f"{BASE}/{citation_id}", json={"cite_key": "new-key"}).status_code
        == 409
    )
    assert client.delete(f"{BASE}/{citation_id}").status_code == 204
    assert client.get(BASE).json() == []
    db.expire_all()
    actions = set(
        db.scalars(select(AuditLog.action).where(AuditLog.user_id == test_user.id))
    )
    assert actions >= {"citation.created", "citation.updated", "citation.deleted"}


def test_incomplete_metadata_remains_unverified_and_key_collisions_fail_cleanly(
    client, access_token
):
    authenticate(client, access_token)
    response = client.post(BASE, json={"title": "বাংলা গবেষণা"})
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["cite_key"].startswith("refnd")
    assert result["is_verified"] is False
    assert any("Missing authors" in warning for warning in result["warnings"])
    assert create(client, cite_key=result["cite_key"]).status_code == 409
    other = create(client).json()
    assert (
        client.put(
            f"{BASE}/{other['id']}",
            json={"title": "বাংলা গবেষণা", "year": None, "doi": None},
        ).status_code
        == 409
    )


def test_reference_lists_format_and_exports_never_cross_tenants(
    client, db, test_user, another_user, access_token, another_access_token
):
    authenticate(client, another_access_token)
    foreign = create(client, title="FOREIGN REFERENCE SECRET").json()["id"]
    authenticate(client, access_token)
    own = create(client).json()["id"]
    assert client.get(BASE).json()[0]["id"] == own
    assert "FOREIGN REFERENCE SECRET" not in client.get(BASE).text
    assert client.put(f"{BASE}/{foreign}", json={"title": "Attack"}).status_code == 404
    assert client.delete(f"{BASE}/{foreign}").status_code == 404
    assert (
        client.post(
            BASE + "/format", json={"citation_ids": [own, foreign], "style": "apa"}
        ).status_code
        == 404
    )
    assert (
        client.get(
            BASE + "/export", params=[("citation_ids", str(foreign))]
        ).status_code
        == 404
    )
    formatted = client.post(
        BASE + "/format", json={"citation_ids": [own], "style": "ieee"}
    )
    assert (
        formatted.status_code == 200
        and formatted.json()["entries"][0]["in_text"] == "[1]"
    )
    for format, media in (
        ("bibtex", "application/x-bibtex"),
        ("ris", "application/x-research-info-systems"),
    ):
        response = client.get(BASE + "/export", params={"format": format})
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith(media)
        assert response.headers["cache-control"] == "private, no-store"
        assert "attachment" in response.headers["content-disposition"]
        assert "FOREIGN REFERENCE SECRET" not in response.text


def test_owned_library_import_uses_canonical_metadata_and_refuses_foreign_links(
    client, db, test_user, another_user, access_token
):
    own, _, _ = indexed_paper(db, test_user.id)
    foreign, _, _ = indexed_paper(db, another_user.id)
    canonical = Paper(
        title="Canonical source",
        doi="10.1234/canonical",
        publication_date=date(2026, 1, 1),
        publication_type="article",
    )
    author = Author(display_name="Ada Lovelace", normalized_name="ada lovelace")
    db.add_all([canonical, author])
    db.flush()
    db.add(PaperAuthor(paper_id=canonical.id, author_id=author.id, position=0))
    db.add(
        PaperSource(
            paper_id=canonical.id, provider="crossref", external_id="10.1234/canonical"
        )
    )
    own.paper_id = canonical.id
    db.commit()
    authenticate(client, access_token)
    assert client.post(BASE, json={"user_paper_id": foreign.id}).status_code == 404
    result = client.post(BASE, json={"user_paper_id": own.id})
    assert result.status_code == 201, result.text
    result = result.json()
    assert result["title"] == "Canonical source" and result["authors"] == [
        "Ada Lovelace"
    ]
    assert result["is_verified"] is True and result["user_paper_id"] == own.id
    # Free-standing reference metadata survives removal of the saved library paper.
    db.execute(delete(ResearchPaper).where(ResearchPaper.id == own.legacy_paper_id))
    db.commit()
    assert client.get(BASE).json()[0]["user_paper_id"] is None


def test_library_sync_attaches_existing_unlinked_doi_reference(
    client, db, test_user, access_token
):
    item, _, _ = indexed_paper(db, test_user.id)
    canonical = Paper(
        title=MANUAL["title"], doi=MANUAL["doi"], publication_date=date(2026, 1, 1)
    )
    db.add(canonical)
    db.flush()
    item.paper_id = canonical.id
    db.commit()
    authenticate(client, access_token)
    original = create(client).json()
    assert original["user_paper_id"] is None
    response = client.post(BASE, json={"user_paper_id": item.id})
    assert response.status_code == 201, response.text
    assert response.json()["id"] == original["id"]
    assert response.json()["user_paper_id"] == item.id
    assert len(client.get(BASE).json()) == 1


def test_doi_lookup_mocked_external_metadata_and_manual_edit_revokes_verification(
    client, access_token
):
    authenticate(client, access_token)
    gateway = client.app.state.discovery_gateway
    gateway.lookup_doi = AsyncMock(
        return_value=DiscoveryPaper(
            title="Verified DOI source",
            authors=["Ada Lovelace"],
            publication_date=date(2026, 2, 1),
            doi="10.1234/provider",
            source="crossref",
            paper_type="article",
        )
    )
    response = client.post(BASE, json={"doi": "https://doi.org/10.1234/PROVIDER"})
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["is_verified"] is True and result["warnings"] == []
    gateway.lookup_doi.assert_awaited_once_with("10.1234/provider")
    response = client.put(
        f"{BASE}/{result['id']}", json={"title": "Manually changed title"}
    )
    assert response.status_code == 200 and response.json()["is_verified"] is False


def test_client_added_fields_do_not_inherit_doi_provider_verification(
    client, access_token
):
    authenticate(client, access_token)
    client.app.state.discovery_gateway.lookup_doi = AsyncMock(
        return_value=DiscoveryPaper(
            title="Verified paper",
            authors=["Ada Lovelace"],
            publication_date=date(2026, 1, 1),
            doi="10.1234/verification",
            source="crossref",
        )
    )
    response = client.post(
        BASE,
        json={
            "doi": "10.1234/verification",
            "venue": "Invented venue",
            "volume": "999",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["is_verified"] is False
    assert any(
        "not been verified" in warning for warning in response.json()["warnings"]
    )


@pytest.mark.parametrize(
    "error,status",
    [(PaperNotFound("none"), 404), (ProviderUnavailable("crossref"), 503)],
)
def test_doi_lookup_errors_are_safe(client, access_token, error, status):
    authenticate(client, access_token)
    client.app.state.discovery_gateway.lookup_doi = AsyncMock(side_effect=error)
    assert client.post(BASE, json={"doi": "10.1234/absent"}).status_code == status


@pytest.mark.parametrize(
    "format,content",
    [
        (
            "bibtex",
            "@article{test2026, title={Imported research}, author={Ada Lovelace}, "
            "year={2026}, doi={10.1234/imported}}",
        ),
        (
            "ris",
            "TY  - JOUR\nID  - test2026\nTI  - Imported research\nAU  - Ada Lovelace\n"
            "PY  - 2026\nDO  - 10.1234/imported\nER  -",
        ),
    ],
)
def test_import_is_atomic_and_deduplicates_every_format(
    client, db, access_token, format, content
):
    authenticate(client, access_token)
    response = client.post(
        BASE + "/import", json={"format": format, "content": content}
    )
    assert response.status_code == 201, response.text
    assert response.json()["created"] == 1 and response.json()["duplicates"] == 0
    assert (
        client.post(
            BASE + "/import", json={"format": format, "content": content}
        ).json()["duplicates"]
        == 1
    )
    count = len(client.get(BASE).json())
    bad = (
        content + "\n@article{broken"
        if format == "bibtex"
        else content + "\nTY  - JOUR\nTI  - Missing end"
    )
    assert (
        client.post(
            BASE + "/import", json={"format": format, "content": bad}
        ).status_code
        == 422
    )
    assert len(client.get(BASE).json()) == count


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", BASE),
        ("POST", BASE),
        ("PUT", BASE + "/1"),
        ("DELETE", BASE + "/1"),
        ("POST", BASE + "/import"),
        ("POST", BASE + "/format"),
        ("GET", BASE + "/export"),
    ],
)
def test_reference_routes_require_live_authentication(client, method, path):
    assert client.request(method, path).status_code == 401


def test_owner_and_verification_cannot_be_assigned_by_client(client, access_token):
    authenticate(client, access_token)
    assert create(client, user_id=999).status_code == 422
    assert create(client, is_verified=True).status_code == 422
    assert create(client, title="Header\nTY  - JOUR").status_code == 422
