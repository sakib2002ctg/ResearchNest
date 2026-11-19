import json

import httpx
import pytest
from fastapi import HTTPException

from app.core.config import settings
from app.modules.ai.gateway import AIProviderGateway, HTTPProvider, system_prompt
from app.modules.rag.retrieval import cosine, terms


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("protocol", ["ollama", "openai"])
async def test_http_provider_contracts_mocked_only(protocol):
    seen = []
    generation = {
        "interpretation": "Tentative synthesis",
        "citations": [
            {"chunk_id": 7, "quoted_snippet": "Photosynthesis converts sunlight"}
        ],
        "follow_up_questions": ["Which evidence is missing?"],
    }

    def handle(request):
        seen.append(request)
        if protocol == "ollama":
            return httpx.Response(
                200,
                json={
                    "message": {"content": json.dumps(generation)},
                    "prompt_eval_count": 20,
                    "eval_count": 10,
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(generation)}}],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
            },
        )

    provider = HTTPProvider(
        "local",
        "http://local.test",
        "test-model",
        protocol=protocol,
        api_key="mock-secret",
        transport=httpx.MockTransport(handle),
    )
    result = await provider.generate(
        [{"role": "system", "content": system_prompt("bn")}], []
    )
    assert result.prompt_tokens == 20 and result.completion_tokens == 10
    assert result.generation.citations[0].chunk_id == 7
    assert seen[0].url.path == (
        "/api/chat" if protocol == "ollama" else "/chat/completions"
    )
    assert seen[0].headers["Authorization"] == "Bearer mock-secret"
    payload = json.loads(seen[0].content)
    assert payload["stream"] is False
    assert payload["model"] == "test-model"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure",
    [
        "timeout",
        "redirect",
        "server",
        "malformed",
        "oversized",
        "bad_usage",
        "bad_followup",
    ],
)
async def test_gateway_bounded_failures_fall_back_to_extracts(failure):
    calls = []

    def handle(request):
        calls.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("mock timeout")
        if failure == "redirect":
            return httpx.Response(
                302, headers={"Location": "https://external.test/stolen"}
            )
        if failure == "server":
            return httpx.Response(503)
        if failure == "oversized":
            return httpx.Response(200, content=b"a" * 70000)
        if failure == "malformed":
            return httpx.Response(200, json={"choices": []})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "follow_up_questions": (
                                        ["x" * 201] if failure == "bad_followup" else []
                                    )
                                }
                            )
                        }
                    }
                ],
                "usage": {"prompt_tokens": -1 if failure == "bad_usage" else 1},
            },
        )

    provider = HTTPProvider(
        "local",
        "http://local.test",
        "test-model",
        transport=httpx.MockTransport(handle),
    )
    gateway = AIProviderGateway(local=provider)
    result = await gateway.generate(
        provider, [], [{"chunk_id": 1, "content": "A verified source passage."}]
    )
    assert result.provider == "offline"
    assert result.generation.citations[0].chunk_id == 1
    assert len(calls) == 1  # no redirects, retries, or external fallback


def test_consent_routes_never_silently_promote_cloud(monkeypatch):
    gateway = AIProviderGateway()
    with pytest.raises(HTTPException) as denied:
        gateway.route("cloud", False)
    assert denied.value.status_code == 403
    assert gateway.route("cloud", True) is gateway.cloud
    monkeypatch.setattr(settings, "AI_DEFAULT_PROVIDER", "auto")
    assert gateway.route("auto", False) is gateway.local
    monkeypatch.setattr(settings, "AI_DEFAULT_PROVIDER", "cloud")
    with pytest.raises(HTTPException):
        gateway.route("auto", False)


def test_multilingual_terms_and_vector_guards():
    assert "সালোকসংশ্লেষণ" in terms("সালোকসংশ্লেষণ সম্পর্কে বলুন।")
    assert "the" not in terms("the photosynthesis")
    assert cosine([1, 0], [1, 0]) == 1
    assert cosine([1], [1, 0]) == 0
    assert cosine([0, 0], [0, 0]) == 0
    assert cosine([1, 0], [float("nan"), 0]) == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("CLOUD_AI_BASE_URL", "file:///tmp/ai"),
        ("CLOUD_AI_BASE_URL", "https://secret:password@example.com/v1"),
        ("OLLAMA_BASE_URL", "http://localhost:11434?token=secret"),
    ],
)
def test_provider_endpoint_settings_reject_credentials_and_unsafe_urls(field, value):
    from pydantic import ValidationError

    from app.core.config import Settings

    with pytest.raises(ValidationError):
        Settings(
            APP_NAME="test",
            DATABASE_URL="sqlite://",
            SECRET_KEY="test",
            **{field: value},
        )
