import asyncio

from scripts.benchmark_api import benchmark_app
from tests.modules.operations.test_operations import application


def test_offline_latency_concurrency_sanity_is_below_p95_target(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "API_RATE_LIMIT_TEST_ENABLED", False)
    result = asyncio.run(
        benchmark_app(
            application(),
            samples=64,
            concurrency=4,
            paths=["/health", "/api/v1/items/benchmark"],
        )
    )
    assert result["samples"] == 64
    assert result["passed"] is True
    assert result["latency_ms"]["p95"] < 500
    assert result["requests_per_second"] > 0
