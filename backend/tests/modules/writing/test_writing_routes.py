from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models.assistant import AIUsage
from app.models.user_preference import UserPreference
from app.models.writing import WritingVersion
from app.modules.ai.gateway import StructuredResult
from app.modules.writing.schemas import DraftOutput, DraftParagraph
from tests.modules.ai.test_assistant import authenticate
from tests.modules.analysis.test_routes import paper

BASE = "/api/v1/writing"


def create(client, **values):
    return client.post(
        BASE, json={"doc_type": "research_paper", "title": "Private draft", **values}
    )


def citation(client, paper_id=None):
    payload = (
        {"user_paper_id": paper_id}
        if paper_id
        else {
            "title": "Real reference",
            "authors": ["Sakib Test"],
            "year": 2026,
            "venue": "Journal",
        }
    )
    response = client.post("/api/v1/citations", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_crud_checkpoint_autosave_restore_and_revision_conflict(
    client, db, access_token
):
    authenticate(client, access_token)
    created = create(client, content_markdown="Original text.")
    assert created.status_code == 201, created.text
    draft = created.json()
    did = draft["id"]
    assert draft["word_count"] == 2 and draft["revision"] == 1
    assert "Methodology" in draft["outline"]
    versions = client.get(f"{BASE}/{did}/versions").json()
    assert len(versions) == 1 and versions[0]["version_number"] == 1
    saved = client.put(
        f"{BASE}/{did}",
        json={"content_markdown": "Edited text now.", "expected_revision": 1},
    ).json()
    assert saved["word_count"] == 3 and saved["revision"] == 2
    assert len(client.get(f"{BASE}/{did}/versions").json()) == 1
    assert (
        client.put(
            f"{BASE}/{did}", json={"title": "Stale", "expected_revision": 1}
        ).status_code
        == 409
    )
    saved = client.put(
        f"{BASE}/{did}",
        json={
            "content_markdown": "Major saved draft.",
            "create_version": True,
            "expected_revision": 2,
        },
    ).json()
    assert len(client.get(f"{BASE}/{did}/versions").json()) == 2
    restored = client.post(
        f"{BASE}/{did}/versions/{versions[0]['id']}/restore",
        json={"expected_revision": 3},
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["content_markdown"] == "Original text."
    history = client.get(f"{BASE}/{did}/versions").json()
    assert [v["version_number"] for v in history] == [4, 3, 2, 1]
    assert history[1]["content_markdown"] == "Major saved draft."
    assert len(client.get(BASE).json()) == 1
    assert client.delete(f"{BASE}/{did}").status_code == 204
    assert client.get(f"{BASE}/{did}").status_code == 404
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(WritingVersion)) == 0


def test_citation_insertion_real_owned_only_and_deleted_reference_export_fails(
    client, access_token
):
    authenticate(client, access_token)
    ref = citation(client)
    draft = create(client, content_markdown=f"Evidence [@{ref['cite_key']}].").json()
    assert draft["cited_citation_ids"] == [ref["id"]]
    assert create(client, content_markdown="Invented [@fake2099].").status_code == 422
    assert (
        client.put(
            f"{BASE}/{draft['id']}", json={"content_markdown": "Bad [@broken key]"}
        ).status_code
        == 422
    )
    assert client.delete(f"/api/v1/citations/{ref['id']}").status_code == 204
    assert client.get(f"{BASE}/{draft['id']}/export").status_code in (404, 422)


def test_tenant_isolation_across_every_private_path(
    client, access_token, another_access_token
):
    authenticate(client, another_access_token)
    foreign = citation(client)
    draft = create(
        client, content_markdown=f"SECRET PRIVATE [@{foreign['cite_key']}]"
    ).json()
    did = draft["id"]
    vid = client.get(f"{BASE}/{did}/versions").json()[0]["id"]
    authenticate(client, access_token)
    assert client.get(BASE).json() == []
    for method, suffix, payload in [
        ("GET", "", None),
        ("PUT", "", {"title": "Stolen"}),
        ("DELETE", "", None),
        ("GET", "/versions", None),
        ("POST", f"/versions/{vid}/restore", {}),
        ("GET", "/export", None),
        ("POST", "/assist", {"action": "grammar", "text": "Secret"}),
    ]:
        response = client.request(
            method,
            f"{BASE}/{did}{suffix}",
            **({"json": payload} if payload is not None else {}),
        )
        assert response.status_code == 404 and "SECRET PRIVATE" not in response.text
    assert create(client, cited_citation_ids=[foreign["id"]]).status_code == 404


@pytest.mark.parametrize(
    "format,magic",
    [("md", b"#"), ("tex", b"\\documentclass"), ("docx", b"PK"), ("pdf", b"%PDF")],
)
def test_export_endpoints_are_private_attachments(client, access_token, format, magic):
    authenticate(client, access_token)
    ref = citation(client)
    draft = create(
        client, content_markdown=f"A cited finding [@{ref['cite_key']}]."
    ).json()
    response = client.get(f"{BASE}/{draft['id']}/export?format={format}&style=ieee")
    assert response.status_code == 200, response.text[:300]
    if format == "tex":
        assert b"\\documentclass" in response.content
        assert b"\\end{document}" in response.content
    else:
        assert response.content.startswith(magic)
    assert response.headers["cache-control"] == "private, no-store"
    assert "attachment" in response.headers["content-disposition"]


def test_source_grounded_suggestion_is_separate_and_idempotent(
    client, db, test_user, access_token
):
    item, _, _ = paper(db, test_user.id)
    authenticate(client, access_token)
    ref = citation(client, item.id)
    draft = create(client, content_markdown="My original authored text.").json()
    did = draft["id"]
    payload = {
        "action": "draft_section",
        "section": "methodology",
        "user_paper_ids": [item.id],
        "request_id": str(uuid4()),
    }
    response = client.post(f"{BASE}/{did}/assist", json=payload)
    assert response.status_code == 200, response.text
    suggestion = response.json()
    assert (
        suggestion["kind"] == "ai_generated_suggestion"
        and suggestion["requires_review"]
    )
    assert f"[@{ref['cite_key']}]" in suggestion["content_markdown"]
    assert suggestion["evidence_links"][0]["page_number"] == 4
    assert suggestion["citation_ids"] == [ref["id"]]
    assert client.post(f"{BASE}/{did}/assist", json=payload).json() == suggestion
    after = client.get(f"{BASE}/{did}").json()
    assert (
        after["content_markdown"] == draft["content_markdown"]
        and after["revision"] == 1
    )
    assert len(after["ai_suggestions_log"]) == 1
    assert client.get("/api/v1/ai/usage").json()["daily"]["requests"] == 1
    db.expire_all()
    assert (
        db.scalar(select(AIUsage).where(AIUsage.user_id == test_user.id)).feature
        == "writing"
    )


def test_missing_results_and_unlinked_sources_are_not_invented(
    client, db, test_user, access_token
):
    item, _, _ = paper(
        db,
        test_user.id,
        text="Methodology: We used a small survey to collect responses.",
    )
    authenticate(client, access_token)
    did = create(client).json()["id"]
    payload = {
        "action": "draft_section",
        "section": "results_discussion",
        "user_paper_ids": [item.id],
    }
    assert client.post(f"{BASE}/{did}/assist", json=payload).status_code == 409
    citation(client, item.id)
    result = client.post(f"{BASE}/{did}/assist", json=payload).json()
    assert (
        "Insufficient" in result["content_markdown"] and result["evidence_links"] == []
    )


@pytest.mark.parametrize("action", ["tone", "grammar", "paraphrase"])
def test_offline_copy_editing_is_honest_and_preserves_authored_text(
    client, access_token, action
):
    authenticate(client, access_token)
    did = create(
        client, language="bn", content_markdown="আমার নিজস্ব গবেষণার লেখা।"
    ).json()["id"]
    result = client.post(
        f"{BASE}/{did}/assist",
        json={"action": action, "text": "আমার নিজস্ব গবেষণার লেখা।"},
    )
    assert result.status_code == 200, result.text
    assert result.json()["content_markdown"] == "আমার নিজস্ব গবেষণার লেখা।"


class FakeProvider:
    name = "cloud"
    model = "mock"

    def __init__(self, output):
        self.output = output
        self.calls = []

    async def generate_structured(self, messages, passages, schema):
        self.calls.append(messages)
        return StructuredResult(self.output, "cloud", "mock", 100, 50)


def test_cloud_consent_quota_and_invented_results_fail_closed(
    client, db, test_user, access_token, monkeypatch
):
    authenticate(client, access_token)
    did = create(client, content_markdown="Accuracy was 90 percent.").json()["id"]
    fake = FakeProvider(
        DraftOutput(paragraphs=[DraftParagraph(text="Accuracy was 99 percent.")])
    )
    client.app.state.ai_gateway.cloud = fake
    request = {
        "action": "grammar",
        "text": "Accuracy was 90 percent.",
        "provider": "cloud",
    }
    assert client.post(f"{BASE}/{did}/assist", json=request).status_code == 403
    assert fake.calls == []
    db.add(UserPreference(user_id=test_user.id, allow_external_ai=True))
    db.commit()
    response = client.post(f"{BASE}/{did}/assist", json=request)
    assert response.status_code == 502, response.text
    assert client.get(f"{BASE}/{did}").json()["ai_suggestions_log"] == []
    monkeypatch.setattr(settings, "AI_DAILY_REQUEST_LIMIT", 1)
    assert client.post(f"{BASE}/{did}/assist", json=request).status_code == 429
    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", BASE),
        ("POST", BASE),
        ("GET", BASE + "/1"),
        ("PUT", BASE + "/1"),
        ("DELETE", BASE + "/1"),
        ("GET", BASE + "/1/versions"),
        ("POST", BASE + "/1/versions/1/restore"),
        ("POST", BASE + "/1/assist"),
        ("GET", BASE + "/1/export"),
    ],
)
def test_all_routes_require_live_authentication(client, method, path):
    assert client.request(method, path).status_code == 401


@pytest.mark.parametrize(
    "fields",
    [
        {"title": "bad\u0000title"},
        {"outline": ["bad\u0000section"]},
        {"content_markdown": "bad\u0000content"},
        {"ai_suggestions_log": []},
        {"user_id": 2},
    ],
)
def test_draft_validation_rejects_controls_and_server_managed_fields(
    client, access_token, fields
):
    authenticate(client, access_token)
    assert create(client, **fields).status_code == 422
