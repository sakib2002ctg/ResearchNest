import pytest
from pydantic import ValidationError

from app.core.config import Settings


@pytest.mark.parametrize("origin", ["http://localhost:3000", "http://127.0.0.1:3000"])
def test_allowed_cors_preflight(client, origin):
    response = client.options(
        "/api/v1/users/me",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"
    assert "Origin" in response.headers["vary"]
    assert "PUT" in response.headers["access-control-allow-methods"]
    assert "Authorization" in response.headers["access-control-allow-headers"]


def test_untrusted_origin_is_not_allowed(client):
    headers = {
        "Origin": "https://untrusted.example",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/v1/users/me", headers=headers)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_cors_preserves_authentication_failure(client):
    response = client.get(
        "/api/v1/users/me", headers={"Origin": "http://localhost:3000"}
    )
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_preflight_works_for_legacy_aliases(client):
    response = client.options(
        "/papers/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.mark.parametrize(
    "method,requested_headers",
    [("TRACE", "authorization"), ("GET", "x-arbitrary-header")],
)
def test_cors_rejects_unapproved_method_or_header(client, method, requested_headers):
    response = client.options(
        "/api/v1/papers/",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": requested_headers,
        },
    )
    assert response.status_code == 400


def test_configurable_cors_origins(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", '["https://research.example"]')
    config = Settings(
        APP_NAME="test",
        DATABASE_URL="sqlite://",
        SECRET_KEY="cors-test-only",
        _env_file=None,
    )
    assert config.CORS_ORIGINS == ["https://research.example"]


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*.example",
        "https://site.example/path",
        "https://a:b@site.example",
        "https://site.example:invalid",
    ],
)
def test_cors_config_disallows_wildcards_and_non_origins(origin):
    with pytest.raises(ValidationError):
        Settings(
            APP_NAME="test",
            DATABASE_URL="sqlite://",
            SECRET_KEY="cors-test-only",
            CORS_ORIGINS=[origin],
            _env_file=None,
        )
