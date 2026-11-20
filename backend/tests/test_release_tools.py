"""Release tooling tests use fake PostgreSQL executables and mock HTTP only."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "release_tools", ROOT / "scripts/verify_release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def valid_config(**changes):
    values = dict(
        APP_ENV="production",
        SECRET_KEY="8bd64ef127c0935a80cbd94953e17afc749a0bfe7c12ae8063d51da7acb4e8f0",
        DEBUG=False,
        DATABASE_URL="postgresql://app:private-db-secret@localhost/researchnest",
        PGVECTOR_ENABLED=True,
        REDIS_URL="redis://localhost:6379/0",
        API_RATE_LIMIT_ENABLED=True,
        CORS_ORIGINS=["https://research.invalid"],
        JWT_ISSUER="researchnest-api",
        JWT_AUDIENCE="researchnest-client",
        DOCUMENT_WORKER_IN_API=False,
        MULTIMODAL_WORKER_IN_API=False,
        CLAMAV_HOST="scanner.invalid",
        SMTP_HOST="mail.invalid",
        SMTP_PORT=587,
        SMTP_FROM="research@invalid.example",
    )
    values.update(changes)
    return SimpleNamespace(**values)


def test_release_checker_config_only_never_contacts_services_or_claims_launch():
    def forbidden(*args):
        raise AssertionError("configuration-only must not contact services")

    result = release.verify(
        config_only=True,
        settings_loader=valid_config,
        database_probe=forbidden,
        http_probe=forbidden,
    )
    assert result["passed"] and not result["launch_ready"]
    assert result["scope"] == "configuration-only"
    assert "private-db-secret" not in json.dumps(result)


@pytest.mark.parametrize(
    "changes",
    [
        {"APP_ENV": "test"},
        {"SECRET_KEY": "short"},
        {"SECRET_KEY": "0123456789abcdef" * 4},
        {"DEBUG": True},
        {"CORS_ORIGINS": ["http://research.invalid"]},
        {"REDIS_URL": None},
        {"PGVECTOR_ENABLED": False},
        {"API_RATE_LIMIT_ENABLED": False},
        {"DOCUMENT_WORKER_IN_API": True},
        {"MULTIMODAL_WORKER_IN_API": True},
        {"CLAMAV_HOST": None},
        {"SMTP_HOST": None},
        {"JWT_AUDIENCE": ""},
    ],
)
def test_release_checker_rejects_incomplete_production_configuration(changes):
    result = release.verify(
        config_only=True, settings_loader=lambda: valid_config(**changes)
    )
    assert not result["passed"] and not result["launch_ready"]
    if "SECRET_KEY" in changes:
        assert result["checks"]["secret_strength"] is False


def test_release_checker_checks_migration_and_both_health_results():
    result = release.verify(
        settings_loader=valid_config,
        database_probe=lambda *_: True,
        http_probe=lambda *_: {"liveness": True, "readiness": True},
    )
    assert result["passed"] and result["launch_ready"]
    result = release.verify(
        settings_loader=valid_config,
        database_probe=lambda *_: False,
        http_probe=lambda *_: {"liveness": True, "readiness": False},
    )
    assert not result["passed"]
    assert result["checks"]["migration_head"] is False


def test_release_checker_redacts_configuration_and_connection_exceptions():
    def secret_failure(*args):
        raise ValueError("private-secret-token-do-not-print")

    result = release.verify(settings_loader=secret_failure)
    assert not result["passed"]
    assert "private-secret" not in json.dumps(result)
    result = release.verify(
        settings_loader=valid_config,
        database_probe=secret_failure,
        http_probe=secret_failure,
    )
    assert result["checks"]["migration_head"] is False
    assert result["checks"]["readiness"] is False
    assert "private-secret" not in json.dumps(result)


@pytest.mark.parametrize("ready_status", [200, 503])
def test_health_probe_uses_bounded_redirect_free_requests(monkeypatch, ready_status):
    client = httpx.Client
    calls = []

    def respond(request):
        calls.append(request.url.path)
        return (
            httpx.Response(200, json={"status": "ok", "version": "2.0.0"})
            if request.url.path == "/health"
            else httpx.Response(
                ready_status,
                json={"status": "ok" if ready_status == 200 else "degraded"},
            )
        )

    def mock_client(**options):
        assert options["trust_env"] is False and options["follow_redirects"] is False
        assert options["timeout"] == 2
        return client(transport=httpx.MockTransport(respond), **options)

    monkeypatch.setattr(httpx, "Client", mock_client)
    assert release.health_checks("http://localhost:8000", 2) == {
        "liveness": True,
        "readiness": ready_status == 200,
    }
    assert calls == ["/health", "/health/ready"]
    assert release.health_checks("https://user:secret@private.invalid", 2) == {
        "liveness": False,
        "readiness": False,
    }
    assert len(calls) == 2


@pytest.fixture
def shell_tools():
    bash = shutil.which("bash")
    if not bash:
        candidate = Path("C:/Program Files/Git/bin/bash.exe")
        bash = str(candidate) if candidate.exists() else None
    if not bash:
        pytest.skip("Bash is required for offline backup/restore script tests")
    # Isolate shell fixtures inside the workspace, including restore temp files.
    cache = ROOT / "backend" / ".cache"
    cache.mkdir(exist_ok=True)
    tmp_path = cache / f"release-shell-{uuid4().hex}"
    tmp_path.mkdir(mode=0o755)
    tools = tmp_path / "fake-tools"
    tools.mkdir()
    programs = {
        "pg_dump": """#!/usr/bin/env bash
printf 'dump %s\\n' "$*" >>"$CALL_LOG"
if [[ ${FAIL_DUMP:-0} == 1 ]]; then
 printf 'private-db-secret' >&2; exit 3
fi
for argument in "$@"; do
 if [[ $argument == --file=* ]]; then
  printf 'PGDMP offline fixture\\n' >"${argument#--file=}"
 fi
done
""",
        "pg_restore": """#!/usr/bin/env bash
printf 'restore %s\\n' "$*" >>"$CALL_LOG"
if [[ $1 == --list ]]; then [[ $(head -c5 "$2") == PGDMP ]]; fi
""",
    }
    for name, source in programs.items():
        path = tools / name
        path.write_text(source, encoding="utf-8", newline="\n")
        path.chmod(0o700)
    log = tmp_path / "calls.log"
    env = {
        **os.environ,
        "FAKE_PG_BIN": str(tools),
        "CALL_LOG": log.as_posix(),
        "TMPDIR": tmp_path.as_posix(),
        "PGDATABASE": "researchnest_restore_test",
    }

    def run(script, archive, confirmation="", extra_env=None):
        environment = {
            **env,
            **(extra_env or {}),
            "RELEASE_SCRIPT": (ROOT / "scripts" / script).as_posix(),
            "ARCHIVE": archive.as_posix(),
        }
        result = subprocess.run(
            [
                bash,
                "-c",
                "if command -v cygpath >/dev/null; then "
                'FAKE_PG_BIN=$(cygpath -u "$FAKE_PG_BIN"); '
                'RELEASE_SCRIPT=$(cygpath -u "$RELEASE_SCRIPT"); '
                'ARCHIVE=$(cygpath -u "$ARCHIVE"); '
                'CALL_LOG=$(cygpath -u "$CALL_LOG"); '
                'TMPDIR=$(cygpath -u "$TMPDIR"); '
                "export CALL_LOG TMPDIR; fi; "
                'export PATH="$FAKE_PG_BIN:$PATH"; '
                'exec bash "$RELEASE_SCRIPT" "$ARCHIVE"',
            ],
            # Raw LF matters: text-mode Windows pipes translate it to CRLF,
            # which must not silently satisfy a strict destructive confirmation.
            input=confirmation.encode("utf-8"),
            capture_output=True,
            env=environment,
            timeout=15,
        )
        result.stdout = result.stdout.decode("utf-8", errors="replace")
        result.stderr = result.stderr.decode("utf-8", errors="replace")
        return result

    try:
        yield run, log, tmp_path
    finally:
        assert tmp_path.resolve().is_relative_to(cache.resolve())
        shutil.rmtree(tmp_path)


def test_backup_and_restore_success_with_checksum_and_safe_flags(shell_tools):
    run, log, directory = shell_tools
    archive = directory / "snapshot with spaces.dump"
    backup = run("backup_db.sh", archive, "BACKUP\n")
    assert backup.returncode == 0, backup.stderr
    expected = hashlib.sha256(archive.read_bytes()).hexdigest()
    assert Path(str(archive) + ".sha256").read_text().strip() == expected
    if os.name != "nt":
        assert archive.stat().st_mode & 0o077 == 0
    restore = run("restore_db.sh", archive, "RESTORE researchnest_restore_test\n")
    assert restore.returncode == 0, restore.stderr
    calls = log.read_text()
    assert "--format=custom" in calls and "--single-transaction" in calls
    assert "--exit-on-error" in calls and "--no-owner" in calls and "--no-acl" in calls
    assert "--no-password" in calls


def test_backup_never_overwrites_or_publishes_failed_dump(shell_tools):
    run, log, directory = shell_tools
    archive = directory / "snapshot.dump"
    archive.write_bytes(b"existing")
    assert run("backup_db.sh", archive, "BACKUP\n").returncode != 0
    assert archive.read_bytes() == b"existing" and not log.exists()
    second = directory / "failed.dump"
    result = run("backup_db.sh", second, "BACKUP\n", {"FAIL_DUMP": "1"})
    assert result.returncode != 0 and not second.exists()
    assert "private-db-secret" not in result.stdout + result.stderr
    assert "dump " in log.read_text()
    assert not list(directory.glob(".researchnest-*"))


@pytest.mark.parametrize(
    "case", ["corrupt", "missing-checksum", "bad-checksum", "cancel", "wrong-target"]
)
def test_restore_verifies_before_any_database_mutation(shell_tools, case):
    run, log, directory = shell_tools
    archive = directory / "snapshot.dump"
    assert run("backup_db.sh", archive, "BACKUP\n").returncode == 0
    log.write_text("")
    confirmation = "RESTORE researchnest_restore_test\n"
    checksum = Path(str(archive) + ".sha256")
    if case == "corrupt":
        archive.write_bytes(b"altered")
    elif case == "missing-checksum":
        checksum.unlink()
    elif case == "bad-checksum":
        checksum.write_text("not a digest")
    elif case == "cancel":
        confirmation = "NO\n"
    else:
        confirmation = "RESTORE wrong_target\n"
    result = run("restore_db.sh", archive, confirmation)
    assert result.returncode != 0
    assert "--single-transaction" not in log.read_text()
