import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.time import utc_now
from app.models.assistant import AIUsage, Message, MessageCitation
from app.models.audit_log import AuditLog
from app.models.document_intelligence import DocumentChunk, Embedding
from app.models.library import Collection, CollectionPaper, Document
from app.models.paper import UserPaper
from app.models.research_paper import ResearchPaper
from app.models.user_preference import UserPreference
from app.modules.ai.gateway import CitationClaim, Generation, ProviderResult
from app.modules.ai.schemas import Question
from app.modules.ai.service import send_message
from app.modules.documents.embeddings import HashEmbeddingProvider

BASE = "/api/v1/conversations"
TEXT = (
    "Photosynthesis converts sunlight into chemical energy in plants. "
    "Chlorophyll absorbs light."
)


def indexed_paper(
    db, owner, *, text=TEXT, title="Plant energy", page=3, model="hash-384"
):
    legacy = ResearchPaper(owner_id=owner, title=title)
    db.add(legacy)
    db.flush()
    paper = UserPaper(user_id=owner, legacy_paper_id=legacy.id)
    db.add(paper)
    db.flush()
    document = Document(
        user_id=owner,
        user_paper_id=paper.id,
        storage_key=f"{uuid4().hex}.pdf",
        original_filename="paper.pdf",
        size_bytes=100,
        sha256="0" * 64,
        page_count=page,
        status="completed",
        version=1,
    )
    db.add(document)
    db.flush()
    chunk = DocumentChunk(
        document_id=document.id,
        user_id=owner,
        document_version=1,
        page_number=page,
        chunk_index=0,
        section_heading="Results",
        content=text,
        token_count=20,
    )
    db.add(chunk)
    db.flush()
    db.add(
        Embedding(
            chunk_id=chunk.id,
            user_id=owner,
            document_version=1,
            model_name=model,
            vector_json=HashEmbeddingProvider().embed([text])[0],
        )
    )
    db.commit()
    return paper, document, chunk


def authenticate(client, token):
    client.headers["Authorization"] = f"Bearer {token}"


def create(client, paper_ids, **kwargs):
    return client.post(
        BASE,
        json={
            "scope_type": "single_paper" if len(paper_ids) == 1 else "selected_papers",
            "scope_paper_ids": paper_ids,
            **kwargs,
        },
    )


def ask(client, chat, content="How does photosynthesis convert sunlight?", **kwargs):
    return client.post(f"{BASE}/{chat}/messages", json={"content": content, **kwargs})


def test_offline_rag_exact_citations_history_usage_and_delete(
    client, db, test_user, access_token
):
    paper, doc, chunk = indexed_paper(db, test_user.id)
    authenticate(client, access_token)
    response = create(client, [paper.id])
    assert response.status_code == 201, response.text
    chat = response.json()["id"]
    answer = ask(client, chat)
    assert answer.status_code == 200, answer.text
    answer = answer.json()
    assert answer["evidence_status"] == "supported"
    assert answer["provider_used"] == "offline"
    citation = answer["citations"][0]
    assert citation["chunk_id"] == chunk.id
    assert citation["document_id"] == doc.id
    assert citation["paper_title"] == "Plant energy"
    assert citation["page_number"] == 3
    assert citation["section_heading"] == "Results"
    assert citation["quoted_snippet"] in TEXT
    assert "[Plant energy, p. 3]" in answer["content"]
    assert answer["interpretation"] == ""
    assert len(answer["follow_up_questions"]) == 2
    history = client.get(f"{BASE}/{chat}")
    assert history.headers["cache-control"] == "private, no-store"
    assert [m["role"] for m in history.json()["messages"]] == ["user", "assistant"]
    assert len(client.get(BASE).json()) == 1
    usage = client.get("/api/v1/ai/usage").json()
    assert usage["hourly"]["requests"] == usage["daily"]["requests"] == 1
    assert usage["hourly"]["tokens"] > 0
    assert usage["active_requests"] == 0
    db.expire_all()
    logs = list(db.scalars(select(AuditLog).where(AuditLog.user_id == test_user.id)))
    assert {entry.action for entry in logs} >= {
        "ai.conversation.created",
        "ai.generation.completed",
    }
    assert TEXT not in str([entry.details for entry in logs])
    db.commit()
    assert client.delete(f"{BASE}/{chat}").status_code == 204
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Message)) == 0
    assert db.scalar(select(func.count()).select_from(MessageCitation)) == 0
    assert (
        db.scalar(select(func.count()).select_from(AIUsage)) == 1
    )  # cannot reset quota by deleting a chat


def test_cross_tenant_scope_rag_and_history_isolation(
    client, db, test_user, another_user, access_token, another_access_token
):
    own, _, own_chunk = indexed_paper(db, test_user.id)
    foreign, _, foreign_chunk = indexed_paper(
        db,
        another_user.id,
        text="Photosynthesis secret code TENANT_B_SECRET.",
        title="B private",
    )
    authenticate(client, another_access_token)
    foreign_chat = create(client, [foreign.id]).json()["id"]
    ask(client, foreign_chat)
    authenticate(client, access_token)
    assert create(client, [foreign.id]).status_code == 404
    assert create(client, [own.id, foreign.id]).status_code == 404
    for method, suffix in (("GET", ""), ("DELETE", ""), ("POST", "/messages")):
        response = client.request(
            method,
            f"{BASE}/{foreign_chat}{suffix}",
            **({"json": {"content": "photosynthesis"}} if method == "POST" else {}),
        )
        assert response.status_code == 404
        assert "TENANT_B_SECRET" not in response.text
    chat = create(client, [own.id]).json()["id"]
    answer = ask(client, chat)
    assert "TENANT_B_SECRET" not in answer.text
    assert [c["chunk_id"] for c in answer.json()["citations"]] == [own_chunk.id]
    assert all(c["id"] != foreign_chat for c in client.get(BASE).json())
    assert client.get("/api/v1/ai/usage").json()["daily"]["requests"] == 1
    db.expire_all()
    # Persistence rejects foreign sources even if service checks are bypassed.
    answer_id = answer.json()["id"]
    db.add(
        MessageCitation(
            user_id=test_user.id,
            message_id=answer_id,
            user_paper_id=foreign.id,
            chunk_id=foreign_chunk.id,
            paper_title="B private",
            page_number=1,
            quoted_snippet="SECRET",
            relevance_score=1,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.parametrize(
    "content",
    [
        "Quantum entanglement black holes",
        "অর্থনীতি মুদ্রাস্ফীতি",
        "photosynthesis cures cancer tumors",
    ],
)
def test_absent_topics_never_call_provider_or_invent_citations(
    client, db, test_user, access_token, content
):
    paper, _, _ = indexed_paper(db, test_user.id)
    authenticate(client, access_token)
    chat = create(client, [paper.id]).json()["id"]
    result = ask(client, chat, content).json()
    assert result["evidence_status"] == "insufficient_evidence"
    assert result["citations"] == []
    assert result["model_used"] == "no-evidence"


def test_bangla_unicode_evidence_and_empty_index(client, db, test_user, access_token):
    paper, doc, _ = indexed_paper(
        db,
        test_user.id,
        text="সালোকসংশ্লেষণ প্রক্রিয়ায় উদ্ভিদ সূর্যালোক থেকে শক্তি উৎপন্ন করে।",
        title="উদ্ভিদের শক্তি",
        page=2,
    )
    authenticate(client, access_token)
    chat = create(client, [paper.id], language="bn").json()["id"]
    result = ask(client, chat, "সালোকসংশ্লেষণ প্রক্রিয়ায় শক্তি").json()
    assert result["evidence_status"] == "supported"
    assert result["citations"][0]["paper_title"] == "উদ্ভিদের শক্তি"
    assert result["citations"][0]["page_number"] == 2
    db.expire_all()
    db.get(Document, doc.id).version = 2
    db.commit()
    result = ask(client, chat, "সালোকসংশ্লেষণ প্রক্রিয়ায় শক্তি").json()
    assert result["evidence_status"] == "insufficient_evidence"
    assert "পর্যাপ্ত প্রমাণ নেই" in result["content"]
    assert result["citations"] == []


def test_collection_scope_checks_and_dynamic_membership(
    client, db, test_user, another_user, access_token
):
    paper, _, _ = indexed_paper(db, test_user.id)
    other, _, _ = indexed_paper(
        db,
        test_user.id,
        title="Out of scope",
        text="Photosynthesis forbidden outside scope.",
    )
    collection = Collection(user_id=test_user.id, name="Plants")
    foreign = Collection(user_id=another_user.id, name="Foreign")
    db.add_all([collection, foreign])
    db.flush()
    db.add(
        CollectionPaper(
            user_id=test_user.id, collection_id=collection.id, user_paper_id=paper.id
        )
    )
    db.commit()
    authenticate(client, access_token)
    assert (
        create(
            client, [], scope_type="collection", scope_collection_id=foreign.id
        ).status_code
        == 404
    )
    chat = create(
        client, [], scope_type="collection", scope_collection_id=collection.id
    ).json()["id"]
    result = ask(client, chat).json()
    assert [c["user_paper_id"] for c in result["citations"]] == [paper.id]
    assert other.id not in [c["user_paper_id"] for c in result["citations"]]
    db.execute(
        delete(CollectionPaper).where(CollectionPaper.collection_id == collection.id)
    )
    db.commit()
    assert ask(client, chat).json()["evidence_status"] == "insufficient_evidence"
    db.execute(delete(Collection).where(Collection.id == collection.id))
    db.commit()
    assert ask(client, chat).status_code == 404


class FakeProvider:
    name = "cloud"
    model = "mock-model"

    def __init__(self, make=None):
        self.calls = []
        self.make = make

    async def generate(self, messages, passages):
        self.calls.append((messages, passages))
        generation = (
            self.make(passages)
            if self.make
            else Generation(
                interpretation="A tentative synthesis.",
                citations=[
                    CitationClaim(
                        chunk_id=p["chunk_id"], quoted_snippet=p["content"][:50]
                    )
                    for p in passages
                ],
            )
        )
        return ProviderResult(generation, self.name, self.model, 100, 50)


def test_cloud_consent_is_fail_closed_and_prompt_separates_instructions(
    client, db, test_user, access_token
):
    paper, _, _ = indexed_paper(db, test_user.id)
    fake = FakeProvider()
    client.app.state.ai_gateway.cloud = fake
    authenticate(client, access_token)
    chat = create(client, [paper.id], language="bn").json()["id"]
    result = ask(client, chat, provider="cloud")
    assert result.status_code == 403 and "Settings" in result.text
    assert not fake.calls
    assert client.get("/api/v1/ai/usage").json()["daily"]["requests"] == 0
    db.add(UserPreference(user_id=test_user.id, allow_external_ai=True))
    db.commit()
    result = ask(client, chat, provider="cloud")
    assert result.status_code == 200, result.text
    assert result.json()["evidence_status"] == "partial_interpretation"
    messages, passages = fake.calls[0]
    assert "বাংলায়" in messages[0]["content"]
    assert TEXT not in messages[0]["content"] and TEXT in messages[1]["content"]
    assert passages[0]["paper_title"] == "Plant energy"
    db.expire_all()
    db.scalar(
        select(UserPreference).where(UserPreference.user_id == test_user.id)
    ).allow_external_ai = False
    db.commit()
    assert ask(client, chat, provider="cloud").status_code == 403
    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    "attack", ["foreign_id", "fabricated_quote", "inline_citation", "no_citations"]
)
def test_unverified_model_output_fails_closed(
    client, db, test_user, access_token, attack
):
    paper, _, _ = indexed_paper(db, test_user.id)

    def make(passages):
        p = passages[0]
        if attack == "no_citations":
            return Generation(interpretation="An invented unsupported answer")
        return Generation(
            interpretation=(
                "See [Imaginary Paper, p. 99]"
                if attack == "inline_citation"
                else "Tentative."
            ),
            citations=[
                CitationClaim(
                    chunk_id=999999 if attack == "foreign_id" else p["chunk_id"],
                    quoted_snippet=(
                        "This invented quote is not in the document."
                        if attack == "fabricated_quote"
                        else p["content"][:50]
                    ),
                )
            ],
        )

    fake = FakeProvider(make)
    fake.name = "local"
    client.app.state.ai_gateway.local = fake
    authenticate(client, access_token)
    chat = create(client, [paper.id]).json()["id"]
    result = ask(client, chat, provider="local").json()
    assert result["evidence_status"] == "insufficient_evidence"
    assert result["citations"] == [] and result["interpretation"] == ""


def test_quota_before_provider_and_idempotent_request_replay(
    client, db, test_user, access_token, monkeypatch
):
    paper, _, _ = indexed_paper(db, test_user.id)
    monkeypatch.setattr(settings, "AI_HOURLY_REQUEST_LIMIT", 1)
    authenticate(client, access_token)
    chat = create(client, [paper.id]).json()["id"]
    request_id = str(uuid4())
    first = ask(client, chat, request_id=request_id)
    assert first.status_code == 200
    replay = ask(client, chat, request_id=request_id)
    assert replay.json() == first.json()
    assert (
        ask(
            client, chat, "Different photosynthesis question", request_id=request_id
        ).status_code
        == 409
    )
    denied = ask(client, chat)
    assert denied.status_code == 429 and denied.headers["Retry-After"] == "60"
    assert client.get("/api/v1/ai/usage").json()["hourly"]["requests"] == 1
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Message)) == 2


@pytest.mark.parametrize(
    "setting",
    ["AI_HOURLY_TOKEN_LIMIT", "AI_DAILY_TOKEN_LIMIT", "AI_DAILY_REQUEST_LIMIT"],
)
def test_token_and_daily_limits(
    client, db, test_user, access_token, monkeypatch, setting
):
    paper, _, _ = indexed_paper(db, test_user.id)
    monkeypatch.setattr(settings, setting, 1)
    authenticate(client, access_token)
    chat = create(client, [paper.id]).json()["id"]
    if setting.endswith("REQUEST_LIMIT"):
        assert ask(client, chat).status_code == 200
    assert ask(client, chat).status_code == 429


def test_concurrent_reservations_and_replay_only_call_provider_once(
    client, db, test_user, access_token
):
    paper, _, _ = indexed_paper(db, test_user.id)
    authenticate(client, access_token)
    chat = create(client, [paper.id]).json()["id"]
    owner = test_user.id
    db.commit()

    async def run():
        from fastapi import HTTPException

        factory = client.app.state.discovery_session_factory
        gateway = client.app.state.ai_gateway
        started, finish = asyncio.Event(), asyncio.Event()
        fake = FakeProvider()
        fake.name = "local"
        original = fake.generate

        async def slow(messages, passages):
            started.set()
            await finish.wait()
            return await original(messages, passages)

        fake.generate = slow
        gateway.local = fake

        async def send(request_id):
            async with factory() as session:
                return await send_message(
                    session,
                    owner,
                    chat,
                    Question(
                        content="photosynthesis sunlight",
                        provider="local",
                        request_id=request_id,
                    ),
                    gateway,
                )

        request = str(uuid4())
        first = asyncio.create_task(send(request))
        await asyncio.wait_for(started.wait(), 5)
        try:
            with pytest.raises(HTTPException) as pending:
                await send(str(uuid4()))
            assert pending.value.status_code == 429
            with pytest.raises(HTTPException) as replay:
                await send(request)
            assert replay.value.status_code == 409
        finally:
            finish.set()
        result = await first
        assert result["evidence_status"] == "partial_interpretation"
        assert len(fake.calls) == 1

    client.portal.call(run)


def test_stale_reservations_remain_charged_and_failure_does_not_hang(
    client, db, test_user, access_token
):
    paper, _, _ = indexed_paper(db, test_user.id)
    authenticate(client, access_token)
    chat = create(client, [paper.id]).json()["id"]
    db.add(
        AIUsage(
            user_id=test_user.id,
            conversation_id=chat,
            request_id=str(uuid4()),
            request_fingerprint="f" * 64,
            feature="rag_chat",
            provider="local",
            model_name="stale",
            status="pending",
            reserved_tokens=1000,
            created_at=utc_now() - timedelta(minutes=2),
        )
    )
    db.commit()
    assert ask(client, chat).status_code == 200
    db.expire_all()
    assert (
        db.scalar(select(AIUsage).where(AIUsage.model_name == "stale")).status
        == "failed"
    )


@pytest.mark.parametrize("change", ["version", "content", "title"])
def test_source_changes_during_inference_reject_stale_citations(
    client, db, test_user, access_token, change
):
    paper, document, chunk = indexed_paper(db, test_user.id)
    authenticate(client, access_token)
    chat = create(client, [paper.id]).json()["id"]
    db.commit()
    fake = FakeProvider()
    fake.name = "local"
    original = fake.generate

    async def mutate(messages, passages):
        factory = client.app.state.discovery_session_factory
        async with factory() as session:
            if change == "version":
                row = await session.get(Document, document.id)
                row.version += 1
            elif change == "content":
                row = await session.get(DocumentChunk, chunk.id)
                row.content = "A replaced source passage with different contents."
            else:
                row = await session.get(ResearchPaper, paper.legacy_paper_id)
                row.title = "A changed title"
            await session.commit()
        return await original(messages, passages)

    fake.generate = mutate
    client.app.state.ai_gateway.local = fake
    result = ask(client, chat, provider="local")
    assert result.status_code == 409
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(MessageCitation)) == 0
    usage = db.scalar(select(AIUsage).where(AIUsage.user_id == test_user.id))
    assert usage.status == "failed" and usage.reserved_tokens > 0


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", BASE),
        ("POST", BASE),
        ("GET", BASE + "/1"),
        ("DELETE", BASE + "/1"),
        ("POST", BASE + "/1/messages"),
        ("GET", "/api/v1/ai/usage"),
    ],
)
def test_all_assistant_routes_require_authentication(client, method, path):
    assert client.request(method, path).status_code == 401


@pytest.mark.parametrize(
    "payload",
    [
        {"scope_type": "single_paper", "scope_paper_ids": []},
        {"scope_type": "single_paper", "scope_paper_ids": [1, 2]},
        {"scope_type": "selected_papers", "scope_paper_ids": [0]},
        {"scope_type": "collection", "scope_paper_ids": [1], "scope_collection_id": 1},
        {"scope_type": "collection"},
        {"scope_type": "single_paper", "scope_paper_ids": [1], "user_id": 2},
    ],
)
def test_invalid_and_client_supplied_owner_scopes_rejected(
    client, access_token, payload
):
    authenticate(client, access_token)
    assert client.post(BASE, json=payload).status_code == 422
