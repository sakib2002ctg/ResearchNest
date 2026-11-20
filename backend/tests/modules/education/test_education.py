from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select, update

from app.core.config import settings
from app.models.assistant import AIUsage
from app.models.audit_log import AuditLog
from app.models.document_intelligence import DocumentChunk, Embedding
from app.models.education import LearningProgress
from app.models.user_preference import UserPreference
from app.modules.ai.gateway import AIProviderGateway, CitationClaim, StructuredResult
from app.modules.education import catalog, service
from app.modules.education.schemas import ExplanationSelection, PlainLanguageSection
from tests.modules.ai.test_assistant import authenticate, indexed_paper

BASE = "/api/v1/education"
TEXT = (
    "Abstract: We examine how plants use sunlight. "
    "Methodology: The baseline compares leaves under different lighting. "
    "Results: Plants in the observed group grew taller. "
    "Limitations: The observations came from a greenhouse."
)


def explain(client, paper_id, **values):
    return client.post(f"{BASE}/explain-paper/{paper_id}", json=values)


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/guides", None),
        ("GET", "/guides/three-pass-reading", None),
        ("POST", "/guides/three-pass-reading/progress", {"completed_step_ids": []}),
        ("GET", "/glossary", None),
        ("POST", "/explain-paper/1", {}),
    ],
)
def test_education_requires_live_authentication(client, method, path, body):
    assert client.request(method, BASE + path, json=body).status_code == 401


def test_catalog_has_complete_bilingual_guides_and_safe_deep_links(
    client, access_token
):
    authenticate(client, access_token)
    response = client.get(f"{BASE}/guides")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    guides = response.json()
    assert len(guides) == 5
    assert len({item["slug"] for item in guides}) == 5
    for guide in guides:
        assert all(guide["title"].values()) and all(guide["summary"].values())
        assert len(guide["steps"]) >= 3
        assert guide["progress"]["percent"] == 0
        assert guide["progress"]["is_completed"] is False
        for step in guide["steps"]:
            assert all(step["title"].values()) and all(step["description"].values())
            assert len(step["checklist"]) >= 2
            assert all(all(check.values()) for check in step["checklist"])
            assert step["module_path"] in {
                "/discover",
                "/library",
                "/analysis",
                "/writing",
            }
        assert all(source["url"].startswith("https://") for source in guide["sources"])
        assert client.get(f"{BASE}/guides/{guide['slug']}").json() == guide
    assert client.get(f"{BASE}/guides/not-a-guide").status_code == 404


def test_progress_persistence_duplicates_uncheck_and_user_isolation(
    client, db, access_token, another_access_token, test_user
):
    authenticate(client, access_token)
    slug = "three-pass-reading"
    path = f"{BASE}/guides/{slug}"
    result = client.post(
        path + "/progress", json={"completed_step_ids": ["orient", "orient"]}
    )
    assert result.status_code == 200, result.text
    assert result.json()["completed_step_ids"] == ["orient"]
    assert result.json()["percent"] == 33.33
    assert datetime.fromisoformat(result.json()["updated_at"]).utcoffset() == timedelta(
        0
    )
    for _ in range(2):
        result = client.post(
            path + "/progress",
            json={"completed_step_ids": ["reconstruct", "orient", "evidence"]},
        )
        assert result.json()["completed_step_ids"] == [
            "orient",
            "evidence",
            "reconstruct",
        ]
        assert result.json()["is_completed"] is True and result.json()["percent"] == 100
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(LearningProgress)) == 1
    db.rollback()
    authenticate(client, another_access_token)
    assert client.get(path).json()["progress"]["completed_step_ids"] == []
    assert (
        client.post(
            path + "/progress", json={"completed_step_ids": ["evidence"]}
        ).status_code
        == 200
    )
    authenticate(client, access_token)
    assert client.get(path).json()["progress"]["is_completed"] is True
    result = client.post(path + "/progress", json={"completed_step_ids": []})
    assert result.json()["percent"] == 0 and result.json()["is_completed"] is False
    assert (
        client.post(
            path + "/progress", json={"completed_step_ids": ["forged"]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            path + "/progress", json={"completed_step_ids": [], "user_id": test_user.id}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"{BASE}/guides/missing/progress", json={"completed_step_ids": []}
        ).status_code
        == 404
    )


def test_progress_sanitizes_obsolete_catalog_steps(client, db, test_user, access_token):
    db.add(
        LearningProgress(
            user_id=test_user.id,
            guide_slug="three-pass-reading",
            completed_step_ids=["deleted-step"],
            is_completed=True,
        )
    )
    db.commit()
    authenticate(client, access_token)
    progress = client.get(f"{BASE}/guides/three-pass-reading").json()["progress"]
    assert progress["completed_step_ids"] == [] and progress["is_completed"] is False


@pytest.mark.parametrize(
    "q,slug",
    [
        ("hypothesis", "hypothesis"),
        ("অনুমান", "hypothesis"),
        ("পি-মান", "p-value"),
        ("HYPOTHESIS", "hypothesis"),
        ("DOI", "doi"),
    ],
)
def test_glossary_searches_both_languages(client, access_token, q, slug):
    authenticate(client, access_token)
    result = client.get(f"{BASE}/glossary", params={"q": q}).json()
    assert slug in {item["slug"] for item in result["items"]}


def test_glossary_categories_examples_and_unknown_filters(client, access_token):
    authenticate(client, access_token)
    all_terms = client.get(f"{BASE}/glossary").json()
    assert len(all_terms["items"]) >= 18
    assert len({item["slug"] for item in all_terms["items"]}) == len(all_terms["items"])
    for item in all_terms["items"]:
        assert all(item["term"].values()) and all(item["definition"].values())
        assert all(item["example"].values())
    for category in all_terms["categories"]:
        filtered = client.get(f"{BASE}/glossary", params={"category": category}).json()
        assert filtered["items"] and all(
            item["category"] == category for item in filtered["items"]
        )
    assert (
        client.get(f"{BASE}/glossary", params={"category": "missing"}).json()["items"]
        == []
    )
    assert (
        client.get(f"{BASE}/glossary", params={"q": "not-a-term-12345"}).json()["items"]
        == []
    )
    assert client.get(f"{BASE}/glossary", params={"q": "x" * 201}).status_code == 422


@pytest.mark.parametrize("language", ["en", "bn"])
def test_offline_explanation_preserves_source_facts_and_tracks_usage(
    client, db, test_user, access_token, language
):
    paper, document, chunk = indexed_paper(db, test_user.id, text=TEXT)
    authenticate(client, access_token)
    response = explain(client, paper.id, language=language, provider="offline")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["provider_used"] == "offline" and result["language"] == language
    assert result["evidence_status"] == "supported"
    assert result["plain_language_interpretation"] == []
    assert len(result["follow_up_questions"]) == 4
    assert result["term_explanations"]
    assert result["mode_notice"]
    assert (
        "উৎস" in result["beginner_explanation"]
        if language == "bn"
        else "source-grounded" in result["beginner_explanation"]
    )
    for evidence in result["supported_evidence"]:
        assert evidence["quoted_snippet"] in TEXT
        assert (
            evidence["chunk_id"] == chunk.id and evidence["document_id"] == document.id
        )
        assert evidence["document_version"] == 1 and evidence["page_number"] == 3
    assert response.headers["cache-control"] == "private, no-store"
    assert "storage_key" not in response.text
    db.expire_all()
    usage = db.scalar(select(AIUsage).where(AIUsage.user_id == test_user.id))
    assert usage.feature == "education" and usage.status == "completed"
    assert usage.prompt_tokens > 0 and usage.completion_tokens > 0
    event = db.scalar(
        select(AuditLog).where(AuditLog.action == "education.paper.explained")
    )
    assert event.user_id == test_user.id
    assert TEXT not in str(event.details)


def test_explanation_rejects_foreign_missing_and_unindexed_papers(
    client, db, another_user, test_user, access_token
):
    foreign, _, _ = indexed_paper(db, another_user.id, text=TEXT)
    own, document, _ = indexed_paper(db, test_user.id, text=TEXT)
    authenticate(client, access_token)
    for pid in (foreign.id, 2147483647):
        assert explain(client, pid).status_code == 404
    document.status = "pending"
    db.commit()
    assert explain(client, own.id).status_code == 409
    document.status = "completed"
    db.execute(delete(Embedding).where(Embedding.user_id == test_user.id))
    db.commit()
    assert explain(client, own.id).status_code == 409
    assert explain(client, 2147483648).status_code == 422
    assert db.scalar(select(func.count()).select_from(AIUsage)) == 0


class PlainProvider:
    name = "local"
    model = "mock-beginner"

    def __init__(self, *, name="local", callback=None, text=None, bad_chunk=False):
        self.name, self.callback, self.text = name, callback, text
        self.bad_chunk, self.calls = bad_chunk, []

    async def generate_structured(self, messages, passages, schema):
        self.calls.append((messages, passages))
        citation = CitationClaim(
            chunk_id=(2147483647 if self.bad_chunk else passages[0]["chunk_id"]),
            quoted_snippet=passages[0]["content"],
        )
        if self.callback:
            self.callback()
        return StructuredResult(
            ExplanationSelection(
                sections=[
                    PlainLanguageSection(
                        focus="question",
                        explanation=self.text
                        or "The researchers examine how lighting relates "
                        "to plant growth.",
                        citations=[citation],
                    )
                ]
            ),
            self.name,
            self.model,
            100,
            50,
        )


@pytest.mark.parametrize(
    "language,text",
    [
        ("en", "The researchers examine how lighting relates to plant growth."),
        ("bn", "গবেষকেরা গাছের বৃদ্ধির সঙ্গে আলোর সম্পর্ক পরীক্ষা করেছেন।"),
        ("bn", "এটি নিশ্চিত সিদ্ধান্ত নয়। গবেষকেরা আলোর প্রভাব পরীক্ষা করেছেন।"),
    ],
)
def test_local_provider_returns_labeled_paper_specific_plain_language(
    client, db, test_user, access_token, language, text
):
    paper, _, _ = indexed_paper(db, test_user.id, text=TEXT)
    adapter = PlainProvider(text=text)
    client.app.state.ai_gateway = AIProviderGateway(local=adapter)
    authenticate(client, access_token)
    result = explain(client, paper.id, language=language, provider="local")
    assert result.status_code == 200, result.text
    result = result.json()
    assert result["evidence_status"] == "partial_interpretation"
    assert result["plain_language_interpretation"][0]["explanation"] == text
    assert (
        result["plain_language_interpretation"][0]["evidence"][0]["quoted_snippet"]
        in TEXT
    )
    assert result["provider_used"] == "local" and len(adapter.calls) == 1
    assert "untrusted data" in adapter.calls[0][0][0]["content"]


@pytest.mark.parametrize(
    "prose",
    [
        "The study showed a 99% improvement in growth.",
        "The result reached ninety nine percent improvement.",
        "The plants grew twenty units taller than the comparison group.",
        "The result is available at https://unverified.example/.",
        "আলোতে গাছের বৃদ্ধি ৯৯ শতাংশ বেশি হয়েছে।",
        "গবেষণায় নয়টি গাছ পরীক্ষা করা হয়েছে।",
    ],
)
def test_hallucinated_numbers_or_references_fail_closed(
    client, db, test_user, access_token, prose
):
    paper, _, _ = indexed_paper(db, test_user.id, text=TEXT)
    client.app.state.ai_gateway = AIProviderGateway(local=PlainProvider(text=prose))
    authenticate(client, access_token)
    response = explain(client, paper.id, provider="local")
    assert response.status_code == 502
    db.expire_all()
    assert db.scalar(select(AIUsage.status)) == "failed"


def test_invalid_source_citation_fails_closed(client, db, test_user, access_token):
    paper, _, _ = indexed_paper(db, test_user.id, text=TEXT)
    client.app.state.ai_gateway = AIProviderGateway(local=PlainProvider(bad_chunk=True))
    authenticate(client, access_token)
    assert explain(client, paper.id, provider="local").status_code == 502


def test_cloud_requires_current_consent_and_explanation_respects_quota(
    client, db, test_user, access_token, monkeypatch
):
    paper, _, _ = indexed_paper(db, test_user.id, text=TEXT)
    cloud = PlainProvider(name="cloud")
    client.app.state.ai_gateway = AIProviderGateway(cloud=cloud)
    authenticate(client, access_token)
    assert explain(client, paper.id, provider="cloud").status_code == 403
    assert cloud.calls == []
    db.add(UserPreference(user_id=test_user.id, allow_external_ai=True))
    db.commit()
    assert explain(client, paper.id, provider="cloud").status_code == 200
    assert len(cloud.calls) == 1
    monkeypatch.setattr(settings, "AI_HOURLY_REQUEST_LIMIT", 1)
    assert explain(client, paper.id, provider="offline").status_code == 429
    assert len(cloud.calls) == 1


def test_same_uuid_and_cross_feature_uuid_never_charge_twice(
    client, db, test_user, access_token
):
    paper, _, _ = indexed_paper(db, test_user.id, text=TEXT)
    authenticate(client, access_token)
    request_id = str(uuid4())
    assert explain(client, paper.id, request_id=request_id).status_code == 200
    assert explain(client, paper.id, request_id=request_id).status_code == 409
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(AIUsage)) == 1
    usage = db.scalar(select(AIUsage))
    usage.feature = "analysis"
    db.commit()
    assert explain(client, paper.id, request_id=request_id).status_code == 409


def test_source_change_during_generation_discards_interpretation(
    client, db, test_user, access_token
):
    paper, _, chunk = indexed_paper(db, test_user.id, text=TEXT)

    def mutate():
        db.execute(
            update(DocumentChunk)
            .where(DocumentChunk.id == chunk.id, DocumentChunk.user_id == test_user.id)
            .values(content=TEXT + " Changed.")
        )
        db.commit()

    client.app.state.ai_gateway = AIProviderGateway(
        local=PlainProvider(callback=mutate)
    )
    authenticate(client, access_token)
    result = explain(client, paper.id, provider="local")
    assert result.status_code == 409, result.text
    db.expire_all()
    assert db.scalar(select(AIUsage.status)) == "failed"


def test_static_catalog_objects_are_not_mutated_by_consumers():
    first = catalog.guide("three-pass-reading")
    first["title"]["en"] = "Changed"
    assert catalog.guide("three-pass-reading")["title"]["en"] != "Changed"


def test_structured_completion_budget_matches_actual_gateway_bound(
    client, db, test_user, access_token, monkeypatch
):
    paper, _, _ = indexed_paper(db, test_user.id, text=TEXT)
    adapter = PlainProvider()

    class MissingUsage(PlainProvider):
        async def generate_structured(self, *args):
            result = await super().generate_structured(*args)
            result.prompt_tokens = result.completion_tokens = None
            return result

    adapter = MissingUsage()
    client.app.state.ai_gateway = AIProviderGateway(local=adapter)
    monkeypatch.setattr(settings, "AI_MAX_COMPLETION_TOKENS", 100)
    monkeypatch.setattr(settings, "ANALYSIS_MAX_COMPLETION_TOKENS", 5000)
    monkeypatch.setattr(settings, "AI_HOURLY_TOKEN_LIMIT", 64999)
    authenticate(client, access_token)
    assert explain(client, paper.id, provider="local").status_code == 429
    assert adapter.calls == []
    monkeypatch.setattr(settings, "AI_HOURLY_TOKEN_LIMIT", 100000)
    response = explain(client, paper.id, provider="local")
    assert response.status_code == 200, response.text
    db.expire_all()
    usage = db.scalar(select(AIUsage))
    assert usage.reserved_tokens == 65000
    assert usage.completion_tokens == 5000
    assert usage.prompt_tokens > 0 and len(adapter.calls) == 1


def test_consent_is_rechecked_immediately_before_cloud_dispatch(
    client, db, test_user, access_token, monkeypatch
):
    paper, _, _ = indexed_paper(db, test_user.id, text=TEXT)
    db.add(UserPreference(user_id=test_user.id, allow_external_ai=True))
    db.commit()
    cloud = PlainProvider(name="cloud")
    client.app.state.ai_gateway = AIProviderGateway(cloud=cloud)
    original = service.provider_for_owner
    calls = 0

    async def revoke_before_dispatch(session, owner, gateway, choice):
        nonlocal calls
        calls += 1
        if calls == 2:
            db.execute(
                update(UserPreference)
                .where(UserPreference.user_id == test_user.id)
                .values(allow_external_ai=False)
            )
            db.commit()
        return await original(session, owner, gateway, choice)

    monkeypatch.setattr(service, "provider_for_owner", revoke_before_dispatch)
    authenticate(client, access_token)
    assert explain(client, paper.id, provider="cloud").status_code == 403
    assert cloud.calls == [] and calls == 2
    db.expire_all()
    assert db.scalar(select(AIUsage.status)) == "failed"


def test_local_failure_falls_back_offline_without_cloud_escalation(
    client, db, test_user, access_token
):
    import httpx

    class Unavailable(PlainProvider):
        async def generate_structured(self, *args):
            raise httpx.ConnectError("Unavailable")

    paper, _, _ = indexed_paper(db, test_user.id, text=TEXT)
    cloud = PlainProvider(name="cloud")
    client.app.state.ai_gateway = AIProviderGateway(local=Unavailable(), cloud=cloud)
    authenticate(client, access_token)
    response = explain(client, paper.id, provider="local")
    assert response.status_code == 200, response.text
    assert response.json()["provider_used"] == "offline"
    assert response.json()["plain_language_interpretation"] == []
    assert cloud.calls == []


def test_progress_rejects_empty_and_oversized_step_ids(client, access_token):
    authenticate(client, access_token)
    for invalid in ("", "x" * 101):
        result = client.post(
            f"{BASE}/guides/three-pass-reading/progress",
            json={"completed_step_ids": [invalid]},
        )
        assert result.status_code == 422


def test_duplicate_model_section_focus_fails_closed(
    client, db, test_user, access_token
):
    class Duplicated(PlainProvider):
        async def generate_structured(self, *args):
            result = await super().generate_structured(*args)
            result.payload.sections.append(result.payload.sections[0].model_copy())
            return result

    paper, _, _ = indexed_paper(db, test_user.id, text=TEXT)
    client.app.state.ai_gateway = AIProviderGateway(local=Duplicated())
    authenticate(client, access_token)
    result = explain(client, paper.id, provider="local")
    assert result.status_code == 502, result.text
