"""Behavioral guardrails for factual rewrites and sources changed during inference."""

import pytest
from sqlalchemy import delete, select, update

from app.models.assistant import AIUsage
from app.models.document_intelligence import DocumentChunk
from app.models.library import Document
from app.models.writing import Citation, WritingDocument
from app.modules.ai.gateway import CitationClaim, StructuredResult
from app.modules.writing.schemas import DraftOutput, DraftParagraph
from tests.modules.ai.test_assistant import authenticate
from tests.modules.analysis.test_routes import paper
from tests.modules.writing.test_writing_routes import citation, create

BASE = "/api/v1/writing"


class Provider:
    name = "local"
    model = "integrity-test"

    def __init__(self, make, mutate=None):
        self.make = make
        self.mutate = mutate
        self.calls = 0

    async def generate_structured(self, messages, passages, schema):
        self.calls += 1
        result = self.make(passages)
        if self.mutate:
            await self.mutate()
        return StructuredResult(result, self.name, self.model, 100, 50)


def output(text):
    return DraftOutput(paragraphs=[DraftParagraph(text=text)])


def assert_no_suggestion_or_draft_change(client, db, doc_id, authored):
    result = client.get(f"{BASE}/{doc_id}").json()
    assert result["content_markdown"] == authored
    assert result["ai_suggestions_log"] == []
    db.expire_all()
    usages = list(db.scalars(select(AIUsage)))
    assert len(usages) == 1 and usages[0].status == "failed"


@pytest.mark.parametrize(
    "original,rewritten",
    [
        (
            "Model A achieved 92 percent accuracy; "
            "Model B achieved 83 percent accuracy.",
            "Model A achieved 83 percent accuracy; "
            "Model B achieved 92 percent accuracy.",
        ),
        (
            "Treatment A did not improve survival. Treatment B improved survival.",
            "Treatment B did not improve survival. Treatment A improved survival.",
        ),
        ("এই কাজ করা সম্ভব।", "এই কাজ করি সম্ভব।"),
    ],
)
def test_copy_edits_cannot_swap_results_negations_or_bangla_vowel_marks(
    client, db, access_token, original, rewritten
):
    authenticate(client, access_token)
    doc_id = create(client, content_markdown=original).json()["id"]
    fake = Provider(lambda _: output(rewritten))
    client.app.state.ai_gateway.local = fake
    response = client.post(
        f"{BASE}/{doc_id}/assist",
        json={"action": "grammar", "provider": "local", "text": original},
    )
    assert response.status_code == 502, response.text
    assert_no_suggestion_or_draft_change(client, db, doc_id, original)


def test_copy_edit_keeps_allowed_punctuation_spacing_and_case_changes_separate(
    client, access_token
):
    authenticate(client, access_token)
    original = "the reported accuracy was 92 percent"
    rewritten = "The reported accuracy was 92 percent."
    doc_id = create(client, content_markdown=original).json()["id"]
    fake = Provider(lambda _: output(rewritten))
    client.app.state.ai_gateway.local = fake
    response = client.post(
        f"{BASE}/{doc_id}/assist",
        json={"action": "grammar", "provider": "local", "text": original},
    )
    assert response.status_code == 200, response.text
    assert response.json()["kind"] == "ai_generated_suggestion"
    assert response.json()["content_markdown"] == rewritten
    assert client.get(f"{BASE}/{doc_id}").json()["content_markdown"] == original


def test_copy_edit_revalidates_original_citation_after_provider_returns(
    client, db, access_token
):
    authenticate(client, access_token)
    reference = citation(client)
    original = f"The source reports a result [@{reference['cite_key']}]."
    doc_id = create(client, content_markdown=original).json()["id"]
    db.commit()

    async def remove_reference():
        factory = client.app.state.discovery_session_factory
        async with factory() as session:
            await session.execute(
                delete(Citation).where(Citation.id == reference["id"])
            )
            await session.commit()

    fake = Provider(lambda _: output(original), remove_reference)
    client.app.state.ai_gateway.local = fake
    response = client.post(
        f"{BASE}/{doc_id}/assist",
        json={"action": "grammar", "provider": "local", "text": original},
    )
    assert response.status_code in (404, 409), response.text
    assert fake.calls == 1
    assert_no_suggestion_or_draft_change(client, db, doc_id, original)


@pytest.mark.parametrize("change", ["version", "chunk", "reference_link", "draft"])
def test_drafting_rechecks_source_reference_and_draft_identity_after_generation(
    client, db, test_user, access_token, change
):
    source, document, chunk = paper(db, test_user.id)
    other_source, _, _ = paper(db, test_user.id, title="Another source")
    authenticate(client, access_token)
    reference = citation(client, source.id)
    original = "My authored text remains under my control."
    doc_id = create(client, content_markdown=original).json()["id"]
    doc_id_value, document_id, chunk_id = doc_id, document.id, chunk.id
    owner_id, other_paper_id = test_user.id, other_source.id
    db.commit()

    def sourced_output(passages):
        chosen = next(p for p in passages if "Methodology" in p["content"])
        return DraftOutput(
            paragraphs=[
                DraftParagraph(
                    text=chosen["content"],
                    evidence=[
                        CitationClaim(
                            chunk_id=chosen["chunk_id"],
                            quoted_snippet=chosen["content"],
                        )
                    ],
                )
            ]
        )

    async def mutate_source():
        factory = client.app.state.discovery_session_factory
        async with factory() as session:
            if change == "version":
                await session.execute(
                    update(Document)
                    .where(Document.user_id == owner_id, Document.id == document_id)
                    .values(version=2)
                )
            elif change == "chunk":
                await session.execute(
                    update(DocumentChunk)
                    .where(
                        DocumentChunk.user_id == owner_id, DocumentChunk.id == chunk_id
                    )
                    .values(
                        content="Methodology: A replacement source has different text."
                    )
                )
            elif change == "reference_link":
                await session.execute(
                    update(Citation)
                    .where(Citation.user_id == owner_id, Citation.id == reference["id"])
                    .values(user_paper_id=other_paper_id)
                )
            else:
                await session.execute(
                    update(WritingDocument)
                    .where(
                        WritingDocument.user_id == owner_id,
                        WritingDocument.id == doc_id_value,
                    )
                    .values(content_markdown="A later user edit.", revision=2)
                )
            await session.commit()

    fake = Provider(sourced_output, mutate_source)
    client.app.state.ai_gateway.local = fake
    response = client.post(
        f"{BASE}/{doc_id}/assist",
        json={
            "action": "draft_section",
            "section": "methodology",
            "user_paper_ids": [source.id],
            "provider": "local",
        },
    )
    assert response.status_code == 409, response.text
    expected = "A later user edit." if change == "draft" else original
    assert_no_suggestion_or_draft_change(client, db, doc_id, expected)


@pytest.mark.parametrize("attack", ["invented_key", "foreign_chunk", "new_result"])
def test_provider_cannot_add_unattributed_reference_or_experimental_results(
    client, db, test_user, access_token, attack
):
    item, _, _ = paper(db, test_user.id)
    authenticate(client, access_token)
    citation(client, item.id)
    original = "An authored outline."
    doc_id = create(client, content_markdown=original).json()["id"]

    def forged_output(passages):
        chosen = next(p for p in passages if "Results:" in p["content"])
        text = chosen["content"]
        chunk_id = chosen["chunk_id"]
        if attack == "invented_key":
            text += " [@invented2099]"
        elif attack == "foreign_chunk":
            chunk_id = 2147483647
        else:
            text = "Our experiment achieved 100 percent accuracy."
        return DraftOutput(
            paragraphs=[
                DraftParagraph(
                    text=text,
                    evidence=[
                        CitationClaim(
                            chunk_id=chunk_id, quoted_snippet=chosen["content"]
                        )
                    ],
                )
            ]
        )

    client.app.state.ai_gateway.local = Provider(forged_output)
    response = client.post(
        f"{BASE}/{doc_id}/assist",
        json={
            "action": "draft_section",
            "section": "results_discussion",
            "user_paper_ids": [item.id],
            "provider": "local",
        },
    )
    assert response.status_code == 502, response.text
    assert_no_suggestion_or_draft_change(client, db, doc_id, original)
