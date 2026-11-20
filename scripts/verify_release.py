"""Read-only release checks. Output deliberately contains no configuration values."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if not (BACKEND / "app").is_dir():
    BACKEND = ROOT


def load_settings():
    sys.path.insert(0, str(BACKEND))
    from app.core.config import Settings, validate_runtime_settings

    config = Settings()
    validate_runtime_settings(config)
    return config


def configuration_checks(config):
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from sqlalchemy.engine import make_url

    from app.core.security_policy import secret_is_strong

    checks = {
        "production_environment": config.APP_ENV == "production",
        "secret_strength": secret_is_strong(config.SECRET_KEY),
        "debug_disabled": not config.DEBUG,
        "postgresql": make_url(config.DATABASE_URL).get_backend_name() == "postgresql",
        "pgvector_enabled": config.PGVECTOR_ENABLED,
        "redis_configured": bool(config.REDIS_URL),
        "rate_limiting_enabled": config.API_RATE_LIMIT_ENABLED,
        "https_origins": bool(config.CORS_ORIGINS)
        and all(urlsplit(origin).scheme == "https" for origin in config.CORS_ORIGINS),
        "jwt_scope": bool(config.JWT_ISSUER and config.JWT_AUDIENCE),
        "separate_workers": not config.DOCUMENT_WORKER_IN_API
        and not config.MULTIMODAL_WORKER_IN_API,
        "pdf_scanner_configured": bool(config.CLAMAV_HOST),
        "email_delivery_configured": bool(
            config.SMTP_HOST and config.SMTP_PORT and config.SMTP_FROM
        ),
    }
    return {key: bool(value) for key, value in checks.items()}


def migration_head_matches(config, timeout):
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    from alembic.config import Config
    from alembic.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url

    alembic_config = Config(str(BACKEND / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(BACKEND / "alembic"))
    expected = set(ScriptDirectory.from_config(alembic_config).get_heads())
    url = make_url(config.DATABASE_URL).set(drivername="postgresql+psycopg2")
    engine = create_engine(
        url,
        connect_args={
            "connect_timeout": max(1, int(timeout)),
            "options": f"-c statement_timeout={int(timeout * 1000)}",
        },
        hide_parameters=True,
    )
    try:
        with engine.connect() as connection:
            actual = set(MigrationContext.configure(connection).get_current_heads())
            return len(expected) == 1 and actual == expected
    finally:
        engine.dispose()


def health_checks(api_url, timeout):
    import httpx

    parsed = urlsplit(api_url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        return {"liveness": False, "readiness": False}
    results = {}
    with httpx.Client(
        timeout=timeout, follow_redirects=False, trust_env=False
    ) as client:
        for key, path in (("liveness", "/health"), ("readiness", "/health/ready")):
            try:
                response = client.get(api_url.rstrip("/") + path)
                body = response.json()
                results[key] = response.status_code == 200 and isinstance(body, dict)
                if key == "liveness":
                    results[key] = results[key] and body == {
                        "status": "ok",
                        "version": "2.0.0",
                    }
                else:
                    results[key] = results[key] and body.get("status") in {
                        "ok",
                        "ready",
                    }
            except Exception:
                results[key] = False
    return results


def verify(
    *,
    api_url="http://127.0.0.1:8000",
    timeout=3,
    config_only=False,
    settings_loader=load_settings,
    database_probe=migration_head_matches,
    http_probe=health_checks,
):
    checks = {}
    try:
        config = settings_loader()
        checks = configuration_checks(config)
        checks["settings_valid"] = True
    except Exception:
        # Pydantic/driver exceptions can include secrets. Do not serialize them.
        checks["settings_valid"] = False
    if checks.get("settings_valid") and not config_only:
        try:
            checks["migration_head"] = bool(database_probe(config, timeout))
        except Exception:
            checks["migration_head"] = False
        try:
            checks.update(http_probe(api_url, timeout))
        except Exception:
            checks.update(liveness=False, readiness=False)
    passed = bool(checks) and all(checks.values())
    return {
        "passed": passed,
        "launch_ready": passed and not config_only,
        "scope": "configuration-only" if config_only else "application-release",
        "version": "2.0.0",
        "checks": checks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=3)
    parser.add_argument("--config-only", action="store_true")
    args = parser.parse_args()
    if not 0 < args.timeout <= 10:
        parser.error("--timeout must be positive and no more than 10 seconds")
    result = verify(
        api_url=args.api_url, timeout=args.timeout, config_only=args.config_only
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
