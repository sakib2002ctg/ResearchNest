from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.models.analysis import Analysis, ComparisonPaper
from app.models.assistant import AIUsage
from app.models.audit_log import AuditLog
from app.models.document_intelligence import DocumentChunk
from app.models.library import Document
from app.models.paper import UserPaper
from app.models.research_paper import ResearchPaper
from app.models.user_preference import UserPreference
from app.modules.ai.gateway import StructuredResult
from app.modules.analysis.extraction import offline_comparison, offline_extraction
from app.modules.analysis.schemas import MISSING
from tests.modules.ai.test_assistant import authenticate, indexed_paper

BASE = "/api/v1/analysis"
FULL = "\n".join(
    [
        "Abstract: We study image classification.",
        "Research problem: Low-resource image recognition remains difficult.",
        "Objectives: Classify small images efficiently.",
        "Methodology: We used supervised learning with cross-validation.",
        "Datasets: The MNIST dataset contains handwritten digits.",
        "Models and algorithms: A convolutional model classifies the images.",
        "Evaluation metrics: Accuracy is 97.2 percent.",
        "Results: The classifier reached 97.2 percent accuracy.",
        "Contributions: We provide a compact classification pipeline.",
        "Limitations: The dataset excludes natural scene images.",
        "Future work: Evaluate on diverse natural scene datasets.",
        "Strengths: The compact model needs little memory.",
        "Weaknesses: The model is sensitive to noisy labels.",
    ]
)


def paper(db, owner, text=FULL, title="Compact classifier"):
    item, document, chunk = indexed_paper(db, owner, text=text, title=title, page=4)
    chunk.section_heading = None
    db.commit()
    return item, document, chunk


def analyze(client, paper_id, **options):
    return client.post(f"{BASE}/{paper_id}", json=options)


def compare(client, ids, **options):
    return client.post(f"{BASE}/compare", json={"user_paper_ids": ids, **options})


def test_structured_extraction_evidence_cache_refresh_and_usage(
    client, db, test_user, access_token
):
    item, document, chunk = paper(db, test_user.id)
    authenticate(client, access_token)
    response = analyze(client, item.id)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "completed" and result["is_stale"] is False
    assert "image classification" in result["abstract_summary"]
    assert "Low-resource" in result["research_problem"]
    assert "MNIST" in " ".join(result["datasets"])
    assert "97.2" in " ".join(result["evaluation_metrics"])
    assert "natural scene" in " ".join(result["limitations"])
    assert len(result["field_statuses"]) == 13
    assert all(status == "supported" for status in result["field_statuses"].values())
    assert {e["field"] for e in result["evidence_links"]} == set(
        result["field_statuses"]
    )
    for link in result["evidence_links"]:
        assert link["chunk_id"] == chunk.id and link["page_number"] == 4
        assert link["document_id"] == document.id and link["document_version"] == 1
        assert (
            link["quoted_snippet"] in FULL
            and link["paper_title"] == "Compact classifier"
        )
    assert "source_fingerprint" not in result
    assert response.headers["cache-control"] == "private, no-store"
    assert analyze(client, item.id).json()["id"] == result["id"]
    assert client.get("/api/v1/ai/usage").json()["daily"]["requests"] == 1
    request_id = str(uuid4())
    refresh = analyze(client, item.id, force_refresh=True, request_id=request_id)
    assert refresh.status_code == 200, refresh.text
    assert (
        analyze(client, item.id, force_refresh=True, request_id=request_id).json()
        == refresh.json()
    )
    assert len(client.get(BASE).json()) == 1
    assert client.get(f"{BASE}/{item.id}").json()["status"] == "completed"
    db.expire_all()
    rows = list(db.scalars(select(AIUsage).where(AIUsage.user_id == test_user.id)))
    assert len(rows) == 2 and all(
        u.feature == "analysis" and u.status == "completed" for u in rows
    )
    assert db.scalar(select(func.count()).select_from(Analysis)) == 1


def test_missing_sections_are_explicit_and_never_implied_strengths(
    client, db, test_user, access_token
):
    item, _, _ = paper(
        db,
        test_user.id,
        text="Methodology: We used supervised learning to classify images.",
    )
    authenticate(client, access_token)
    result = analyze(client, item.id).json()
    assert "supervised learning" in result["methodology"]
    assert result["research_problem"] == MISSING
    for field in ("datasets", "strengths", "weaknesses", "limitations", "future_work"):
        assert result[field] == [MISSING]
        assert result["field_statuses"][field] == "not_specified"
        assert not any(e["field"] == field for e in result["evidence_links"])


def test_comparison_matrix_synthesis_gaps_and_replay(
    client, db, test_user, access_token
):
    first, _, _ = paper(db, test_user.id)
    second, _, _ = paper(
        db,
        test_user.id,
        text=FULL.replace("MNIST", "CIFAR").replace("97.2", "92.1"),
        title="Other classifier",
    )
    authenticate(client, access_token)
    request_id = str(uuid4())
    response = compare(client, [first.id, second.id], request_id=request_id)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["user_paper_ids"] == [first.id, second.id]
    assert len(result["comparison_matrix"]) == 2
    assert "MNIST" in str(result["comparison_matrix"][0]["datasets"])
    assert "CIFAR" in str(result["comparison_matrix"][1]["datasets"])
    assert (
        "97.2" in result["literature_synthesis"]
        and "92.1" in result["literature_synthesis"]
    )
    assert result["research_gaps"][0]["scope"] == "selected_papers_only"
    assert (
        len({e["user_paper_id"] for e in result["research_gaps"][0]["evidence_links"]})
        == 2
    )
    assert result["research_gaps"][0]["evidence_status"] == "partial_interpretation"
    assert (
        compare(client, [first.id, second.id], request_id=request_id).json() == result
    )
    assert client.get(f"{BASE}/comparisons/{result['id']}").json() == result
    assert client.get(f"{BASE}/comparisons").json()[0]["id"] == result["id"]
    assert client.get("/api/v1/ai/usage").json()["daily"]["requests"] == 1


def test_no_limitations_does_not_invent_global_research_gaps(
    client, db, test_user, access_token
):
    ids = [
        paper(
            db, test_user.id, text="Methodology: We used regression for classification."
        )[0].id
        for _ in range(2)
    ]
    authenticate(client, access_token)
    result = compare(client, ids).json()
    assert result["research_gaps"] == []
    assert all(row["limitations"] == [MISSING] for row in result["comparison_matrix"])


def test_bangla_extraction_comparison_and_query_options(
    client, db, test_user, access_token
):
    body = (
        "সারসংক্ষেপ: এই গবেষণায় চিত্র শনাক্তকরণ নিয়ে আলোচনা করা হয়েছে।\n"
        "পদ্ধতি: প্রশিক্ষণে তত্ত্বাবধানে শিক্ষণ ব্যবহার করা হয়েছে।\n"
        "সীমাবদ্ধতা: পরীক্ষায় প্রাকৃতিক দৃশ্যের ছবি নেই।\n"
        "ভবিষ্যৎ: বিভিন্ন দৃশ্যের ছবি নিয়ে কাজ করা হবে।"
    )
    ids = [
        paper(db, test_user.id, text=body, title="চিত্র শনাক্তকরণ")[0].id
        for _ in range(2)
    ]
    authenticate(client, access_token)
    response = client.post(f"{BASE}/{ids[0]}?language=bn&force_refresh=true")
    assert response.status_code == 200, response.text
    assert response.json()["language"] == "bn"
    assert "তত্ত্বাবধানে" in response.json()["methodology"]
    assert client.get(f"{BASE}/{ids[0]}?language=bn").status_code == 200
    assert client.get(f"{BASE}/{ids[0]}").status_code == 404
    result = compare(client, ids, language="bn").json()
    assert result["language"] == "bn" and "নির্বাচিত" in result["literature_synthesis"]
    assert "সীমাবদ্ধতা" in result["research_gaps"][0]["title"]


def test_cross_user_reads_writes_scopes_and_membership_denied(
    client, db, test_user, another_user, access_token, another_access_token
):
    own = [paper(db, test_user.id)[0].id for _ in range(2)]
    foreign = [
        paper(db, another_user.id, title="FOREIGN SECRET")[0].id for _ in range(2)
    ]
    authenticate(client, another_access_token)
    assert analyze(client, foreign[0]).status_code == 200
    foreign_comparison = compare(client, foreign).json()["id"]
    authenticate(client, access_token)
    for method in ("GET", "POST"):
        response = client.request(method, f"{BASE}/{foreign[0]}")
        assert response.status_code == 404 and "FOREIGN SECRET" not in response.text
    assert compare(client, [own[0], foreign[0]]).status_code == 404
    assert client.get(f"{BASE}/comparisons/{foreign_comparison}").status_code == 404
    assert client.get(BASE).json() == client.get(f"{BASE}/comparisons").json() == []
    result = compare(client, own).json()
    assert "FOREIGN SECRET" not in str(result)
    db.expire_all()
    db.add(
        ComparisonPaper(
            user_id=test_user.id, comparison_id=result["id"], user_paper_id=foreign[0]
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    # Deleting a scoped paper makes the comparison inaccessible, not partially scoped.
    db.execute(
        delete(ResearchPaper).where(
            ResearchPaper.id == db.get(UserPaper, own[0]).legacy_paper_id
        )
    )
    db.commit()
    assert client.get(f"{BASE}/comparisons/{result['id']}").status_code == 404
    assert client.get(f"{BASE}/comparisons").json() == []


def test_not_uploaded_not_indexed_and_empty_readable_text(
    client, db, test_user, access_token
):
    authenticate(client, access_token)
    created = client.post("/api/v1/papers/", json={"title": "Without PDF"}).json()["id"]
    db.expire_all()
    link = db.scalar(select(UserPaper).where(UserPaper.legacy_paper_id == created))
    db.commit()
    assert analyze(client, link.id).status_code == 409
    item, doc, chunk = paper(db, test_user.id)
    db.get(Document, doc.id).status = "processing"
    db.commit()
    assert analyze(client, item.id).status_code == 409
    db.get(Document, doc.id).status = "completed"
    db.get(DocumentChunk, chunk.id).content = ""
    db.commit()
    assert analyze(client, item.id).status_code == 409


def test_source_reindex_invalidation_and_deleted_pdf_snapshot(
    client, db, test_user, access_token
):
    item, doc, chunk = paper(db, test_user.id)
    authenticate(client, access_token)
    first = analyze(client, item.id).json()
    db.expire_all()
    db.get(Document, doc.id).version = 2
    db.get(DocumentChunk, chunk.id).document_version = 2
    db.get(DocumentChunk, chunk.id).content = (
        "Methodology: We used a different validated procedure."
    )
    db.commit()
    assert client.get(f"{BASE}/{item.id}").json()["is_stale"] is True
    refreshed = analyze(client, item.id).json()
    assert refreshed["id"] == first["id"] and refreshed["document_version"] == 2
    assert refreshed["is_stale"] is False and "different" in refreshed["methodology"]
    db.execute(delete(Document).where(Document.id == doc.id))
    db.commit()
    response = client.get(f"{BASE}/{item.id}").json()
    assert response["document_id"] is None and response["is_stale"] is True


class FakeStructured:
    name = "cloud"
    model = "offline-mock"

    def __init__(self, mutate=None):
        self.calls = []
        self.mutate = mutate

    async def generate_structured(self, messages, passages, schema):
        self.calls.append(messages)
        output = (
            offline_comparison(
                passages,
                list(dict.fromkeys(p["user_paper_id"] for p in passages)),
                "en",
            )
            if schema.__name__ == "ComparisonOutput"
            else offline_extraction(passages)
        )
        if self.mutate:
            self.mutate(output)
        return StructuredResult(output, self.name, self.model, 100, 100)


def test_cloud_consent_and_safe_audit_usage(client, db, test_user, access_token):
    item, _, _ = paper(db, test_user.id)
    fake = FakeStructured()
    client.app.state.ai_gateway.cloud = fake
    authenticate(client, access_token)
    assert analyze(client, item.id, provider="cloud").status_code == 403
    assert fake.calls == []
    db.add(UserPreference(user_id=test_user.id, allow_external_ai=True))
    db.commit()
    result = analyze(client, item.id, provider="cloud")
    assert result.status_code == 200, result.text
    assert result.json()["provider_used"] == "cloud"
    assert (
        "untrusted" in fake.calls[0][0]["content"]
        and FULL not in fake.calls[0][0]["content"]
    )
    db.expire_all()
    log = db.scalar(select(AuditLog).where(AuditLog.action == "analysis.completed"))
    assert FULL not in str(log.details)
    usage = db.scalar(select(AIUsage).where(AIUsage.user_id == test_user.id))
    assert (
        usage.feature == "analysis"
        and usage.prompt_tokens == usage.completion_tokens == 100
    )


@pytest.mark.parametrize(
    "attack",
    ["foreign_chunk", "invented_quote", "invented_technical", "unmentioned_field"],
)
def test_unverified_claims_fail_closed_with_failed_snapshot(
    client, db, test_user, access_token, attack
):
    item, _, _ = paper(
        db,
        test_user.id,
        text="Methodology: We used supervised learning for classification.",
    )

    def mutate(output):
        claim = output.fields["methodology"][0]
        if attack == "foreign_chunk":
            claim.evidence[0].chunk_id = 999999
        if attack == "invented_quote":
            claim.evidence[0].quoted_snippet = "This is a fake source sentence."
        if attack == "invented_technical":
            output.fields["models_and_algorithms"] = [
                claim.model_copy(update={"text": "GPT-unknown"})
            ]
        if attack == "unmentioned_field":
            output.fields["strengths"] = [claim]

    fake = FakeStructured(mutate)
    fake.name = "local"
    client.app.state.ai_gateway.local = fake
    authenticate(client, access_token)
    response = analyze(client, item.id, provider="local")
    assert response.status_code == 502, response.text
    result = client.get(f"{BASE}/{item.id}").json()
    assert result["status"] == "failed" and result["evidence_links"] == []
    assert result["strengths"] == [MISSING]
    db.expire_all()
    assert (
        db.scalar(select(AIUsage).where(AIUsage.user_id == test_user.id)).status
        == "failed"
    )


def test_quota_before_any_provider_call(
    client, db, test_user, access_token, monkeypatch
):
    item, _, _ = paper(db, test_user.id)
    fake = FakeStructured()
    fake.name = "local"
    client.app.state.ai_gateway.local = fake
    monkeypatch.setattr(settings, "AI_DAILY_TOKEN_LIMIT", 1)
    authenticate(client, access_token)
    assert analyze(client, item.id, provider="local").status_code == 429
    assert fake.calls == []


@pytest.mark.parametrize("change", ["version", "text", "consent"])
def test_sources_and_consent_are_rechecked_around_inference(
    client, db, test_user, access_token, change
):
    item, document, chunk = paper(db, test_user.id)
    authenticate(client, access_token)
    fake = FakeStructured()
    fake.name = "local"
    original = fake.generate_structured

    async def mutate(messages, passages, schema):
        factory = client.app.state.discovery_session_factory
        async with factory() as session:
            if change == "version":
                row = await session.get(Document, document.id)
                row.version += 1
            elif change == "text":
                row = await session.get(DocumentChunk, chunk.id)
                row.content = (
                    "Methodology: Replacement text invalidates original sources."
                )
            else:
                # Concurrent unrelated preference updates do not mutate source content.
                session.add(
                    UserPreference(user_id=test_user.id, allow_external_ai=False)
                )
            await session.commit()
        return await original(messages, passages, schema)

    fake.generate_structured = mutate
    client.app.state.ai_gateway.local = fake
    response = analyze(client, item.id, provider="local")
    assert response.status_code == (200 if change == "consent" else 409), response.text
    db.expire_all()
    usage = db.scalar(select(AIUsage).where(AIUsage.user_id == test_user.id))
    assert usage.status == ("completed" if change == "consent" else "failed")


def test_request_id_conflict_and_failed_refresh_preserves_previous_analysis(
    client, db, test_user, access_token
):
    item, _, _ = paper(db, test_user.id)
    authenticate(client, access_token)
    request_id = str(uuid4())
    first = analyze(client, item.id, force_refresh=True, request_id=request_id).json()
    assert (
        analyze(
            client, item.id, force_refresh=True, provider="local", request_id=request_id
        ).status_code
        == 409
    )

    def mutate(output):
        output.fields["methodology"][0].evidence[0].chunk_id = 999999

    fake = FakeStructured(mutate)
    fake.name = "local"
    client.app.state.ai_gateway.local = fake
    assert (
        analyze(client, item.id, force_refresh=True, provider="local").status_code
        == 502
    )
    after = client.get(f"{BASE}/{item.id}").json()
    assert after == first and after["status"] == "completed"


@pytest.mark.parametrize("ids", [[], [1], [1, 1], [0, 1], [1, 2, 3, 4, 5, 6]])
def test_compare_requires_two_to_five_distinct_valid_ids(client, access_token, ids):
    authenticate(client, access_token)
    assert compare(client, ids).status_code == 422


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", BASE),
        ("POST", BASE + "/1"),
        ("GET", BASE + "/1"),
        ("POST", BASE + "/compare"),
        ("GET", BASE + "/comparisons"),
        ("GET", BASE + "/comparisons/1"),
    ],
)
def test_routes_require_live_authentication(client, method, path):
    assert client.request(method, path).status_code == 401
