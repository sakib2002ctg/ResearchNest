import asyncio
import io
import json
import logging
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from redis.exceptions import RedisError

from app.core.config import Settings, settings, validate_runtime_settings
from app.core.logging import SafeJSONFormatter, logger
from app.core.security_policy import secret_is_strong
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import MemorySlidingWindow, RateLimitMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.modules.operations import health
from app.modules.operations.router import router


@pytest.fixture(autouse=True)
def operation_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "API_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "API_RATE_LIMIT_TEST_ENABLED", False)
    monkeypatch.setattr(settings, "API_RATE_LIMIT_REQUESTS", 3)
    monkeypatch.setattr(settings, "API_RATE_LIMIT_WINDOW_SECONDS", 10)
    monkeypatch.setattr(settings, "API_RATE_LIMIT_MAX_CLIENTS", 100)
    monkeypatch.setattr(settings, "READINESS_TIMEOUT_SECONDS", 2.0)
    monkeypatch.setattr(settings, "READINESS_STORAGE_CACHE_SECONDS", 0.0)
    monkeypatch.setattr(settings, "REDIS_URL", None)
    monkeypatch.setattr(settings, "HSTS_ENABLED", True)
    monkeypatch.setattr(settings, "PDF_STORAGE_ROOT", tmp_path / "pdfs")
    monkeypatch.setattr(settings, "ASSET_STORAGE_ROOT", tmp_path / "assets")


class ProbeDatabase:
    def __init__(self, failure=False):
        self.failure = failure

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def execute(self, query):
        assert str(query) == "SELECT 1"
        if self.failure:
            raise RuntimeError("postgresql://private:password@internal/path")


def application():
    app = FastAPI()
    app.include_router(router)
    app.state.discovery_session_factory = ProbeDatabase
    app.state.operational_redis = None

    @app.get("/api/v1/items/{item_id}")
    async def item(item_id: str):
        return {"item": item_id}

    @app.get("/api/v1/denied")
    async def denied():
        raise HTTPException(403, "Denied")

    @app.post("/api/v1/number")
    async def number(value: int):
        return {"value": value}

    @app.get("/api/v1/broken")
    async def broken():
        raise RuntimeError("provider secret password document text")

    for path in ("/papers", "/auth/login", "/research/search"):
        app.add_api_route(path, lambda: {"ok": True}, methods=["GET"])
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://site.example"],
        allow_methods=["GET", "POST"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    return app


@pytest.mark.parametrize(
    "method,path,status",
    [
        ("GET", "/health", 200),
        ("GET", "/unknown", 404),
        ("GET", "/api/v1/denied", 403),
        ("POST", "/api/v1/number?value=invalid", 422),
        ("GET", "/api/v1/broken", 500),
    ],
)
def test_security_headers_cover_success_errors_and_validation(method, path, status):
    with TestClient(application()) as client:
        response = client.request(method, path)
    assert response.status_code == status
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in response.headers["permissions-policy"]
    assert len(response.headers["x-request-id"]) == 36
    assert "strict-transport-security" not in response.headers
    if path.startswith("/api/"):
        assert response.headers["cache-control"] == "private, no-store"
    assert "provider secret" not in response.text


def test_hsts_is_production_only_and_configurable(monkeypatch):
    app = application()
    with TestClient(app) as client:
        monkeypatch.setattr(settings, "APP_ENV", "production")
        monkeypatch.setattr(settings, "HSTS_MAX_AGE", 123)
        assert (
            client.get("/health").headers["strict-transport-security"] == "max-age=123"
        )
        monkeypatch.setattr(settings, "HSTS_ENABLED", False)
        assert "strict-transport-security" not in client.get("/health").headers
        monkeypatch.setattr(settings, "HSTS_ENABLED", True)
        monkeypatch.setattr(settings, "APP_ENV", "staging")
        assert "strict-transport-security" not in client.get("/health").headers


def test_authentication_headers_trigger_private_cache_and_ids_cannot_be_spoofed():
    with TestClient(application()) as client:
        one = client.get(
            "/health",
            headers={"Authorization": "Bearer secret", "X-Request-ID": "attacker-id"},
        )
        two = client.get("/health")
    assert one.headers["cache-control"] == "private, no-store"
    assert one.headers["x-request-id"] != "attacker-id"
    assert one.headers["x-request-id"] != two.headers["x-request-id"]


def test_memory_window_expiry_capacity_and_bounded_entries():
    clock = [0.0]
    limiter = MemorySlidingWindow(lambda: clock[0])
    assert limiter.check("a", 2, 10, 2).allowed
    assert limiter.check("a", 2, 10, 2).allowed
    assert limiter.check("a", 2, 10, 2).retry_after == 10
    clock[0] = 4
    assert limiter.check("a", 2, 10, 2).retry_after == 6
    assert limiter.check("b", 2, 10, 2).allowed
    assert not limiter.check("c", 2, 10, 2).allowed
    assert len(limiter.entries) == 2
    clock[0] = 10
    assert limiter.check("c", 2, 10, 2).allowed
    assert "a" not in limiter.entries


def test_memory_concurrent_admission_is_atomic():
    limiter = MemorySlidingWindow(lambda: 0)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: limiter.check("same", 5, 60, 100), range(24)))
    assert sum(result.allowed for result in results) == 5
    assert len(limiter.entries["same"][0]) == 5


def test_rate_limits_share_budget_across_legacy_and_versioned_routes(monkeypatch):
    monkeypatch.setattr(settings, "API_RATE_LIMIT_TEST_ENABLED", True)
    with TestClient(application()) as client:
        for path in ("/papers", "/api/v1/items/a", "/auth/login"):
            assert client.get(path).status_code == 200
        response = client.get(
            "/research/search",
            headers={
                "Origin": "https://site.example",
                "X-Forwarded-For": "new-spoofed-peer",
                "Authorization": "Bearer rotated-token",
            },
        )
        assert response.status_code == 429
        assert int(response.headers["retry-after"]) >= 1
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["access-control-allow-origin"] == "https://site.example"
        assert all(client.get("/health").status_code == 200 for _ in range(5))


def test_test_bypass_and_explicit_disable(monkeypatch):
    with TestClient(application()) as client:
        assert all(client.get("/papers").status_code == 200 for _ in range(6))
        monkeypatch.setattr(settings, "API_RATE_LIMIT_TEST_ENABLED", True)
        monkeypatch.setattr(settings, "API_RATE_LIMIT_ENABLED", False)
        assert all(client.get("/papers").status_code == 200 for _ in range(6))


def test_preflight_does_not_consume_request_budget(monkeypatch):
    monkeypatch.setattr(settings, "API_RATE_LIMIT_TEST_ENABLED", True)
    with TestClient(application()) as client:
        for _ in range(8):
            assert (
                client.options(
                    "/papers",
                    headers={
                        "Origin": "https://site.example",
                        "Access-Control-Request-Method": "GET",
                    },
                ).status_code
                == 200
            )
        assert client.get("/papers").status_code == 200


@pytest.mark.parametrize("path", ["/api/v1/items/a", "/papers"])
def test_mounted_apps_keep_rate_limit_and_private_cache_policy(monkeypatch, path):
    monkeypatch.setattr(settings, "API_RATE_LIMIT_TEST_ENABLED", True)
    with TestClient(application(), root_path="/mounted") as client:
        for _ in range(3):
            response = client.get("/mounted" + path)
            assert response.status_code == 200
            assert response.headers["cache-control"] == "private, no-store"
        limited = client.get("/mounted" + path)
    assert limited.status_code == 429
    assert limited.headers["cache-control"] == "private, no-store"
    assert limited.headers["x-frame-options"] == "DENY"


def test_post_header_errors_suppress_private_exception_context():
    async def partial(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send(
            {"type": "http.response.body", "body": b"safe prefix", "more_body": True}
        )
        raise ValueError("private document text and credential-secret")

    messages = []

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        messages.append(message)

    scope = {"type": "http", "path": "/api/v1/stream", "headers": []}
    with pytest.raises(RuntimeError, match="Response stream interrupted") as error:
        asyncio.run(SecurityHeadersMiddleware(partial)(scope, receive, send))
    assert type(error.value) is RuntimeError
    rendered = "".join(traceback.format_exception(error.value))
    assert "credential-secret" not in rendered and "private document" not in rendered
    assert error.value.__suppress_context__ is True
    assert (b"x-frame-options", b"DENY") in messages[0]["headers"]


class RedisProbe:
    def __init__(self, result=True, limit_result=None, failure=False):
        self.result = result
        self.limit_result = limit_result or [1, 0]
        self.failure = failure
        self.calls = []

    async def ping(self):
        if self.failure:
            raise RedisError("redis://secret@private-host")
        return self.result

    async def eval(self, *args):
        self.calls.append(args)
        if self.failure:
            raise RedisError("redis://secret@private-host")
        return self.limit_result


def test_redis_backend_uses_atomic_script_and_private_stable_key(monkeypatch):
    monkeypatch.setattr(settings, "API_RATE_LIMIT_TEST_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://test-only")
    app = application()
    redis = RedisProbe(limit_result=[0, 7])
    app.state.operational_redis = redis
    with TestClient(app) as client:
        first = client.get("/papers", headers={"Authorization": "Bearer private-token"})
        second = client.get("/papers", headers={"X-Forwarded-For": "spoofed"})
    assert first.status_code == second.status_code == 429
    assert first.headers["retry-after"] == "7"
    args = redis.calls[0]
    assert "ZREMRANGEBYSCORE" in args[0] and "redis.call('TIME')" in args[0]
    assert args[1] == 1 and args[3:5] == (10000, 3)
    assert args[2] == redis.calls[1][2]
    assert "private-token" not in repr(args) and "testclient" not in args[2]
    assert args[5] != redis.calls[1][5]


@pytest.mark.parametrize("client_exists", [True, False])
def test_redis_outage_fails_closed_without_memory_fallback(monkeypatch, client_exists):
    monkeypatch.setattr(settings, "API_RATE_LIMIT_TEST_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_URL", "redis://configured")
    app = application()
    app.state.operational_redis = RedisProbe(failure=True) if client_exists else None
    with TestClient(app) as client:
        response = client.get("/papers")
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.headers["x-frame-options"] == "DENY"
    assert "secret" not in response.text and "private-host" not in response.text


def test_liveness_is_exact_and_does_not_depend_on_database():
    app = application()
    app.state.discovery_session_factory = lambda: ProbeDatabase(failure=True)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.json() == {"status": "ok", "version": "2.0.0"}
    assert response.status_code == 200


def test_readiness_database_redis_storage_success_and_probe_cleanup(monkeypatch):
    monkeypatch.setattr(settings, "REDIS_URL", "redis://configured")
    app = application()
    app.state.operational_redis = RedisProbe()
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "2.0.0",
        "checks": {"database": "ok", "redis": "ok", "storage": "ok"},
    }
    assert list(settings.PDF_STORAGE_ROOT.iterdir()) == []
    assert list(settings.ASSET_STORAGE_ROOT.iterdir()) == []


@pytest.mark.parametrize("component", ["database", "redis", "storage"])
def test_readiness_degraded_paths_never_expose_details(monkeypatch, component):
    app = application()
    if component == "database":
        app.state.discovery_session_factory = lambda: ProbeDatabase(failure=True)
    elif component == "redis":
        monkeypatch.setattr(settings, "REDIS_URL", "redis://configured")
        app.state.operational_redis = RedisProbe(failure=True)
    else:
        monkeypatch.setattr(health, "storage_writable", lambda root: False)
    with TestClient(app) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"][component] == "unavailable"
    assert response.json()["status"] == "degraded"
    assert all(
        secret not in response.text for secret in ("password", "internal", "storage/")
    )


def test_readiness_timeout_and_disabled_redis(monkeypatch):
    async def blocked(app):
        await asyncio.Event().wait()

    monkeypatch.setattr(health, "database_ready", blocked)
    monkeypatch.setattr(settings, "READINESS_TIMEOUT_SECONDS", 0.01)
    with TestClient(application()) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "unavailable"
    assert response.json()["checks"]["redis"] == "disabled"


def test_storage_probe_rejects_non_directory_and_io_failure(tmp_path, monkeypatch):
    file = tmp_path / "file"
    file.write_bytes(b"not a directory")
    assert not health.storage_writable(file)
    monkeypatch.setattr(
        health.tempfile,
        "mkstemp",
        lambda **kw: (_ for _ in ()).throw(OSError("private")),
    )
    assert not health.storage_writable(tmp_path / "denied")


def test_storage_probe_coalesces_timed_out_requests_without_blocking_liveness(
    monkeypatch,
):
    import httpx

    started, release = threading.Event(), threading.Event()
    calls = []

    def blocked(root):
        calls.append(root)
        started.set()
        release.wait(timeout=5)
        return False

    monkeypatch.setattr(health, "storage_writable", blocked)
    monkeypatch.setattr(settings, "READINESS_TIMEOUT_SECONDS", 0.02)
    app = application()

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test.invalid"
        ) as client:
            first = asyncio.create_task(client.get("/health/ready"))
            assert await asyncio.to_thread(started.wait, 1)
            try:
                rest = await asyncio.gather(
                    *[client.get("/health/ready") for _ in range(20)]
                )
                assert all(response.status_code == 503 for response in rest)
                assert (await first).status_code == 503
                assert (await client.get("/health")).status_code == 200
                assert len(calls) == 1
                # A new client loop or configuration cannot launch another
                # thread while the original filesystem operation is blocked.
                monkeypatch.setattr(
                    settings, "ASSET_STORAGE_ROOT", settings.ASSET_STORAGE_ROOT / "new"
                )
                assert await health.storage_ready(app) is False
                assert len(calls) == 1
            finally:
                release.set()

    asyncio.run(run())


def test_storage_probe_ttl_cache_expires_and_is_loop_agnostic(monkeypatch):
    clock, calls = [10.0], []
    monkeypatch.setattr(settings, "READINESS_STORAGE_CACHE_SECONDS", 1.0)
    monkeypatch.setattr(
        health, "storage_writable", lambda root: calls.append(root) or True
    )
    app = application()
    app.state.readiness_storage_probe = health.StorageProbe(lambda: clock[0])
    assert asyncio.run(health.storage_ready(app)) is True
    assert len(calls) == 2
    assert asyncio.run(health.storage_ready(app)) is True
    assert len(calls) == 2
    clock[0] = 12
    assert asyncio.run(health.storage_ready(app)) is True
    assert len(calls) == 4


def test_structured_request_logs_never_contain_raw_path_query_or_token():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(SafeJSONFormatter())
    logger.addHandler(handler)
    try:
        with TestClient(application()) as client:
            response = client.get(
                "/api/v1/items/private-path?token=query-secret",
                headers={"Authorization": "Bearer bearer-secret"},
            )
        records = [json.loads(line) for line in stream.getvalue().splitlines()]
        request = next(row for row in records if row["message"] == "http.request")
        assert request["route"] == "/api/v1/items/{item_id}"
        assert request["request_id"] == response.headers["x-request-id"]
        assert request["duration_ms"] >= 0
        assert not any(
            secret in stream.getvalue()
            for secret in ("private-path", "query-secret", "bearer-secret")
        )
        error = ValueError("password token private source")
        record = logging.LogRecord(
            "researchnest",
            logging.ERROR,
            "",
            0,
            "Database unavailable.",
            (),
            (ValueError, error, None),
        )
        formatted = SafeJSONFormatter().format(record)
        assert "private source" not in formatted
        assert json.loads(formatted)["error_type"] == "ValueError"
    finally:
        logger.removeHandler(handler)


def production_config(**overrides):
    defaults = dict(
        APP_NAME="test",
        DATABASE_URL="postgresql://service@db/researchnest",
        SECRET_KEY="phase12-Strong-Unique-Key-0123456789-abcdef",
        APP_ENV="production",
        DEBUG=False,
        CORS_ORIGINS=["https://site.example"],
        API_RATE_LIMIT_ENABLED=True,
    )
    return Settings(**(defaults | overrides), _env_file=None)


@pytest.mark.parametrize("environment_value", ["false", "true"])
def test_production_fixture_is_independent_of_test_rate_limit_environment(
    monkeypatch, environment_value
):
    monkeypatch.setenv("API_RATE_LIMIT_ENABLED", environment_value)
    config = production_config()
    assert config.API_RATE_LIMIT_ENABLED is True
    validate_runtime_settings(config)
    with pytest.raises(ValueError, match="rate limiting must be enabled"):
        validate_runtime_settings(production_config(API_RATE_LIMIT_ENABLED=False))


def test_environment_alias_and_valid_production_settings(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "staging")
    config = Settings(
        APP_NAME="test", DATABASE_URL="sqlite://", SECRET_KEY="test", _env_file=None
    )
    assert config.APP_ENV == "staging"
    validate_runtime_settings(production_config())


@pytest.mark.parametrize(
    "override",
    [
        {"SECRET_KEY": "short"},
        {"SECRET_KEY": "a" * 64},
        {"DEBUG": True},
        {"CORS_ORIGINS": ["http://site.example"]},
        {"CORS_ORIGINS": []},
        {"JWT_AUDIENCE": ""},
        {"JWT_ISSUER": ""},
        {"ALGORITHM": "HS512"},
        {"API_RATE_LIMIT_ENABLED": False},
        {"DATABASE_URL": "sqlite://"},
    ],
)
def test_production_runtime_validation_fails_without_echoing_secrets(override):
    with pytest.raises(ValueError) as error:
        validate_runtime_settings(production_config(**override))
    assert "phase12-Strong" not in str(error.value)


def test_non_production_runtime_validation_is_compatible():
    validate_runtime_settings(production_config(APP_ENV="test", SECRET_KEY="test"))


@pytest.mark.parametrize(
    "secret",
    [
        "0123456789abcdef" * 4,
        "0123456789ABCDEF0123456789abcdef",
        "change-me-to-a-real-secret-0123456789abcdef",
        "REPLACE_THIS_WITH_0123456789abcdef_REAL_KEY",
        "your-secret-key-0123456789abcdefghijklmnopqrstuvwxyz",
        "example-production-key-0123456789abcdef",
        "test-secret-with-enough-unique-0123456789abcdef",
        "ci-only-with-enough-unique-0123456789abcdef",
        " " * 16 + "0123456789abcdef" + " " * 16,
    ],
)
def test_secret_policy_rejects_predictable_keys_at_runtime(secret):
    assert secret_is_strong(secret) is False
    with pytest.raises(ValueError, match="SECRET_KEY must be strong") as error:
        validate_runtime_settings(production_config(SECRET_KEY=secret))
    assert secret not in str(error.value)


def test_secret_policy_accepts_nonrepeating_test_fixture_and_rejects_nonstrings():
    # Public deterministic fixture only; deployment keys must be generated.
    fixture = "8bd64ef127c0935a80cbd94953e17afc749a0bfe7c12ae8063d51da7acb4e8f0"
    assert secret_is_strong(fixture) is True
    validate_runtime_settings(production_config(SECRET_KEY=fixture))
    assert secret_is_strong(None) is False
    assert secret_is_strong(123456789) is False
