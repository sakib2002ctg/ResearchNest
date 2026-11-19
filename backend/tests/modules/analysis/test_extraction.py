import json

import httpx
import pytest
from pydantic import ValidationError

from app.modules.ai.gateway import AIProviderGateway, HTTPProvider
from app.modules.analysis.extraction import (
    offline_comparison,
    offline_extraction,
    select_context,
    validate_comparison,
    validate_extraction,
)
from app.modules.analysis.repository import Source
from app.modules.analysis.schemas import MISSING, Claim, Extraction


@pytest.fixture
def anyio_backend():
    return "asyncio"


def source(
    pid=1, cid=1, content="Methodology: We used regression with cross-validation."
):
    return Source(pid, f"Paper {pid}", pid, 1, "0" * 64, cid, 2, None, content)


def test_context_balanced_and_quotes_exact_including_decimals_unicode_and_long_text():
    text = (
        "Metrics: Accuracy is 97.2 percent.\n"
        "পদ্ধতি: এখানে তত্ত্বাবধানে শিক্ষণ ব্যবহার করা হয়েছে।\n"
        + "Long sentence " * 1000
    )
    offered = select_context([source(i, i, text) for i in range(1, 6)])
    assert {p["user_paper_id"] for p in offered} == set(range(1, 6))
    assert sum(len(p["content"]) for p in offered) <= 10000
    assert all(p["content"] in text and 10 <= len(p["content"]) <= 600 for p in offered)
    assert any("97.2" in p["content"] for p in offered)


def test_unrecognized_sections_leave_honest_missing_values():
    offered = select_context(
        [source(content="An otherwise unstructured passage about the environment.")]
    )
    output = offline_extraction(offered)
    values, statuses, evidence = validate_extraction(output, offered, 1)
    assert values["methodology"] == MISSING and values["datasets"] == [MISSING]
    assert set(statuses.values()) == {"not_specified"} and evidence == []


def test_verified_synthesis_is_interpretation_not_direct_quote():
    offered = select_context([source()])
    output = offline_extraction(offered)
    output.fields["methodology"][0].text = "This study applies regression."
    values, statuses, evidence = validate_extraction(output, offered, 1)
    assert statuses["methodology"] == "partial_interpretation"
    assert evidence[0]["page_number"] == 2


@pytest.mark.parametrize(
    "attack", ["paper_id", "quote", "inline", "technical", "absent_section"]
)
def test_claim_verifier_rejects_fabricated_or_unmentioned_attributions(attack):
    offered = select_context([source()])
    output = offline_extraction(offered)
    claim = output.fields["methodology"][0]
    if attack == "paper_id":
        with pytest.raises(ValueError):
            validate_extraction(output, offered, 2)
        return
    if attack == "quote":
        claim.evidence[0].quoted_snippet = "A fabricated quote that does not exist."
    if attack == "inline":
        claim.text = "Read [Fake paper, p. 99] for the method."
    if attack == "technical":
        output.fields["datasets"] = [Claim(text="UnknownData", evidence=claim.evidence)]
    if attack == "absent_section":
        output.fields["strengths"] = [claim]
    with pytest.raises(ValueError):
        validate_extraction(output, offered, 1)


@pytest.mark.parametrize(
    "attack",
    [
        "missing_paper",
        "foreign_paper",
        "one_source",
        "gap_without_limitations",
        "fabricated_synthesis",
    ],
)
def test_comparison_requires_exact_scope_and_two_supported_papers(attack):
    offered = select_context([source(), source(2, 2)])
    output = offline_comparison(offered, [1, 2], "en")
    if attack == "missing_paper":
        output.papers.pop()
    if attack == "foreign_paper":
        output.papers[1].user_paper_id = 3
    if attack == "one_source":
        output.literature_synthesis[0].evidence[1].user_paper_id = 1
    if attack == "gap_without_limitations":
        from app.modules.analysis.schemas import Gap

        output.research_gaps = [
            Gap(
                title="Invented gap",
                text="A supposed gap.",
                evidence=output.literature_synthesis[0].evidence,
            )
        ]
    if attack == "fabricated_synthesis":
        output.literature_synthesis[0].text = "https://fake.test"
    with pytest.raises(ValueError):
        validate_comparison(output, offered, [1, 2])


def test_five_paper_offline_comparison_remains_bounded_and_evidence_backed():
    sources = [
        source(
            i,
            i,
            "Results: Accuracy improves with training.\n"
            "Limitations: The dataset is limited to one region.\n"
            "Future work: Test multilingual generalization.",
        )
        for i in range(1, 6)
    ]
    offered = select_context(sources)
    output = offline_comparison(offered, [1, 2, 3, 4, 5], "en")
    matrix, synthesis, gaps, evidence = validate_comparison(
        output, offered, [1, 2, 3, 4, 5]
    )
    assert len(matrix) == 5 and len(gaps[0]["evidence_links"]) == 5
    assert gaps[0]["scope"] == "selected_papers_only"
    assert len(synthesis[0]) <= 3000


def test_gap_title_cannot_introduce_unverified_citation():
    offered = select_context(
        [
            source(i, i, "Limitations: This study used only one regional dataset.")
            for i in (1, 2)
        ]
    )
    output = offline_comparison(offered, [1, 2], "en")
    output.research_gaps[0].title = "See [Invented source, p. 99]"
    with pytest.raises(ValueError, match="Unverified synthesis"):
        validate_comparison(output, offered, [1, 2])


@pytest.mark.parametrize(
    "payload",
    [
        {"fields": {"invented_field": []}},
        {"fields": {"methodology": [{"text": "hello", "evidence": [], "user_id": 2}]}},
    ],
)
def test_strict_provider_schema(payload):
    with pytest.raises(ValidationError):
        Extraction.model_validate(payload)


@pytest.mark.anyio
@pytest.mark.parametrize("protocol", ["ollama", "openai"])
async def test_shared_gateway_structured_http_contract_is_mocked(protocol):
    offered = select_context([source()])
    output = offline_extraction(offered)
    seen = []

    def handle(request):
        seen.append(json.loads(request.content))
        if protocol == "ollama":
            return httpx.Response(
                200,
                json={
                    "message": {"content": output.model_dump_json()},
                    "prompt_eval_count": 20,
                    "eval_count": 30,
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": output.model_dump_json()}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 30},
            },
        )

    provider = HTTPProvider(
        "local",
        "http://mock.test",
        "mock",
        protocol=protocol,
        transport=httpx.MockTransport(handle),
    )
    gateway = AIProviderGateway(local=provider)
    result = await gateway.generate_structured(
        provider,
        [{"role": "system", "content": "Return JSON."}],
        offered,
        Extraction,
        lambda: output,
    )
    assert (
        result.payload == output
        and result.prompt_tokens == 20
        and result.completion_tokens == 30
    )
    assert result.provider == "local"
    assert (
        seen[0]["options"]["num_predict"]
        if protocol == "ollama"
        else seen[0]["max_tokens"]
    ) == 4096


@pytest.mark.anyio
async def test_unreachable_or_invalid_provider_uses_local_fallback():
    offered = select_context([source()])
    output = offline_extraction(offered)

    def handle(request):
        raise httpx.ConnectError("offline mock")

    provider = HTTPProvider(
        "cloud", "https://mock.test", "mock", transport=httpx.MockTransport(handle)
    )
    gateway = AIProviderGateway(cloud=provider)
    result = await gateway.generate_structured(
        provider, [], offered, Extraction, lambda: output
    )
    assert result.provider == "offline" and result.payload == output
