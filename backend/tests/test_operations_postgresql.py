"""Exercise the real application lifespan/readiness, not just isolated probes."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from tests import test_identity_postgresql

identity_database = test_identity_postgresql.identity_database


def configure(monkeypatch, tmp_path, url):
    monkeypatch.setattr(settings, "APP_ENV", "test")
    monkeypatch.setattr(settings, "DATABASE_URL", url)
    monkeypatch.setattr(settings, "REDIS_URL", None)
    monkeypatch.setattr(settings, "DOCUMENT_EMBEDDING_PROVIDER", "hash")
    monkeypatch.setattr(settings, "PDF_STORAGE_ROOT", tmp_path / "pdfs")
    monkeypatch.setattr(settings, "ASSET_STORAGE_ROOT", tmp_path / "assets")


def test_real_application_readiness_against_postgresql_and_private_storage(
    identity_database, monkeypatch, tmp_path
):
    configure(
        monkeypatch,
        tmp_path,
        identity_database.url.render_as_string(hide_password=False),
    )
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok", "version": "2.0.0"}
        ready = client.get("/health/ready")
        assert ready.status_code == 200, ready.text
        assert ready.json()["checks"] == {
            "database": "ok",
            "storage": "ok",
            "redis": "disabled",
        }
        assert ready.headers["x-content-type-options"] == "nosniff"
    assert not list((tmp_path / "pdfs").glob(".readiness-*"))
    assert not list((tmp_path / "assets").glob(".readiness-*"))


def test_database_outage_does_not_block_real_app_startup_or_liveness(
    monkeypatch, tmp_path
):
    configure(monkeypatch, tmp_path, "sqlite://")
    attempts = []

    class LegacyEngine:
        def connect(self):
            attempts.append(1)
            raise AssertionError("Synchronous startup connections are forbidden")

    monkeypatch.setattr("app.main.engine", LegacyEngine())

    async def unavailable(_app):
        raise RuntimeError("private-database-diagnostic")

    monkeypatch.setattr("app.modules.operations.health.database_ready", unavailable)
    with TestClient(app) as client:
        assert not attempts
        assert client.get("/health").status_code == 200
        ready = client.get("/health/ready")
        assert ready.status_code == 503
        assert ready.json()["checks"]["database"] == "unavailable"
        assert "private-database-diagnostic" not in ready.text
        assert client.get("/health").status_code == 200
