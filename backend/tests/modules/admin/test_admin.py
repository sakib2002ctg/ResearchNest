import json
from datetime import timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.core.time import utc_now
from app.models.assistant import AIUsage
from app.models.audit_log import AuditLog
from app.models.document_intelligence import ProcessingJob
from app.models.library import Document
from app.models.paper import Paper, UserPaper
from app.models.research_paper import ResearchPaper
from app.models.session import Session
from app.models.teams import TeamWorkspace
from app.models.user import User
from app.modules.admin.dependencies import AdminPrincipal, require_admin_user
from app.modules.documents.processing import DocumentProcessor
from tests.conftest import issue_test_session
from tests.modules.ai.test_assistant import indexed_paper

BASE = "/api/v1/admin"
OPERATIONS = [
    ("GET", "/overview"),
    ("GET", "/users"),
    ("GET", "/audit-logs"),
    ("GET", "/jobs/failed"),
    ("POST", "/users/1/revoke-sessions"),
    ("POST", "/jobs/1/requeue"),
]


@pytest.fixture
def administrator(client, db, test_user, access_token):
    test_user.is_admin = True
    db.commit()
    client.headers["Authorization"] = f"Bearer {access_token}"
    return client


def failed_job(
    db,
    owner,
    *,
    status="failed",
    document_status="failed",
    version=1,
    document_version=1,
    attempts=5,
):
    projection = ResearchPaper(owner_id=owner, title="Private source title")
    db.add(projection)
    db.flush()
    saved = UserPaper(
        user_id=owner, legacy_paper_id=projection.id, note="Personal research notes"
    )
    db.add(saved)
    db.flush()
    document = Document(
        user_id=owner,
        user_paper_id=saved.id,
        storage_key=f"{uuid4().hex}.pdf",
        original_filename="private-original.pdf",
        size_bytes=120,
        sha256="a" * 64,
        page_count=1,
        status=document_status,
        version=document_version,
        error_message="Private parser content and file path",
    )
    db.add(document)
    db.flush()
    job = ProcessingJob(
        user_id=owner,
        document_id=document.id,
        document_version=version,
        status=status,
        attempts=attempts,
        last_error="Secret provider text with credentials",
        started_at=utc_now() - timedelta(minutes=20),
        completed_at=utc_now(),
    )
    db.add(job)
    db.commit()
    return job.id, document.id


@pytest.mark.parametrize("method,path", OPERATIONS)
def test_all_admin_operations_require_authentication(client, method, path):
    assert client.request(method, BASE + path).status_code == 401


@pytest.mark.parametrize("method,path", OPERATIONS)
def test_all_admin_operations_forbid_non_admins(authenticated_client, method, path):
    assert authenticated_client.request(method, BASE + path).status_code == 403


def test_authenticated_admin_access_denial_is_safely_audited(
    authenticated_client, db, test_user
):
    response = authenticated_client.get(BASE + "/users?ignored=PRIVATE_QUERY_TOKEN")
    assert response.status_code == 403
    db.expire_all()
    event = db.scalar(select(AuditLog).where(AuditLog.action == "admin.access.denied"))
    assert event.user_id == test_user.id
    # FastAPI retains the nested router's static route template here.
    assert event.details == {"method": "GET", "route": "/admin/users"}
    assert "PRIVATE_QUERY_TOKEN" not in json.dumps(event.details)


def test_registration_and_forged_jwt_cannot_grant_admin(
    client, db, user_payload, access_token, test_user
):
    payload = {
        **user_payload,
        "username": "cannot-promote",
        "email": "new@example.com",
        "is_admin": True,
    }
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    created = db.scalar(select(User).where(User.email == "new@example.com"))
    assert created.is_admin is False
    assert "is_admin" not in response.json()
    session = db.scalar(select(Session).where(Session.user_id == test_user.id))
    token = create_access_token(
        {
            "sub": str(test_user.id),
            "sid": session.id,
            "jti": session.token_jti,
            "is_admin": True,
        }
    )
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get(BASE + "/overview").status_code == 403


@pytest.mark.parametrize(
    "state,expected", [("demoted", 403), ("revoked", 401), ("expired", 401)]
)
def test_async_capability_rechecks_stale_admin_and_session(
    administrator, db, test_user, state, expected
):
    session = db.scalar(select(Session).where(Session.user_id == test_user.id))
    principal = AdminPrincipal(test_user.id, session.id, session.token_jti)
    if state == "demoted":
        test_user.is_admin = False
    elif state == "revoked":
        session.is_revoked = True
    else:
        session.expires_at = utc_now() - timedelta(seconds=1)
    db.commit()
    administrator.app.dependency_overrides[require_admin_user] = lambda: principal
    try:
        assert administrator.get(BASE + "/overview").status_code == expected
        db.expire_all()
        denied = db.scalar(
            select(AuditLog).where(AuditLog.action == "admin.action.denied")
        )
        assert denied.user_id == test_user.id
        assert denied.details == {"operation": "overview.read", "status": expected}
    finally:
        administrator.app.dependency_overrides.pop(require_admin_user, None)


def test_failed_admin_writes_record_only_safe_operation_status_and_ids(
    administrator, db, another_user
):
    missing = 2147483647
    assert (
        administrator.post(BASE + f"/users/{missing}/revoke-sessions").status_code
        == 404
    )
    assert administrator.post(BASE + f"/jobs/{missing}/requeue").status_code == 404
    jid, _ = failed_job(
        db, another_user.id, status="running", document_status="processing"
    )
    assert administrator.post(BASE + f"/jobs/{jid}/requeue").status_code == 409
    db.expire_all()
    records = list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.action == "admin.action.denied")
            .order_by(AuditLog.id)
        )
    )
    assert [(row.resource_type, row.resource_id, row.details) for row in records] == [
        ("user", str(missing), {"operation": "sessions.revoke", "status": 404}),
        ("processing_job", str(missing), {"operation": "job.requeue", "status": 404}),
        ("processing_job", str(jid), {"operation": "job.requeue", "status": 409}),
    ]
    assert "Secret provider" not in json.dumps([row.details for row in records])
    assert not any("detail" in row.details for row in records)


def test_deleted_admin_actor_denial_is_audited_without_dangling_user_fk(
    administrator, db, test_user
):
    session = db.scalar(select(Session).where(Session.user_id == test_user.id))
    actor = AdminPrincipal(test_user.id, session.id, session.token_jti)
    db.delete(test_user)
    db.commit()
    administrator.app.dependency_overrides[require_admin_user] = lambda: actor
    try:
        assert administrator.get(BASE + "/overview").status_code == 401
    finally:
        administrator.app.dependency_overrides.pop(require_admin_user, None)
    db.expire_all()
    record = db.scalar(select(AuditLog).where(AuditLog.action == "admin.action.denied"))
    assert record.user_id is None
    assert record.details == {"operation": "overview.read", "status": 401}


@pytest.mark.parametrize("denied_action", [False, True])
def test_required_audit_write_failure_never_acknowledges_action_or_revokes_sessions(
    administrator, db, another_user, another_access_token, monkeypatch, denied_action
):
    original = AsyncSession.commit

    async def unavailable_audit(session):
        if any(
            isinstance(row, AuditLog)
            and row.action in {"admin.sessions.revoked", "admin.action.denied"}
            for row in session.new
        ):
            raise RuntimeError("PRIVATE_AUDIT_STORE_CREDENTIAL")
        return await original(session)

    monkeypatch.setattr(AsyncSession, "commit", unavailable_audit)
    target = 2147483647 if denied_action else another_user.id
    response = administrator.post(BASE + f"/users/{target}/revoke-sessions")
    assert response.status_code == 500
    assert "PRIVATE_AUDIT_STORE_CREDENTIAL" not in response.text
    db.expire_all()
    active = db.scalar(select(Session).where(Session.user_id == another_user.id))
    assert active.is_revoked is False and active.revoked_at is None
    assert (
        administrator.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {another_access_token}"},
        ).status_code
        == 200
    )


def test_overview_counts_and_safe_operational_metrics(
    administrator, db, test_user, another_user, another_access_token
):
    another_user.is_verified = True
    db.add_all(
        [
            Paper(title="Canonical metadata"),
            TeamWorkspace(owner_id=another_user.id, name="Operational team"),
            AIUsage(
                user_id=another_user.id,
                request_id=str(uuid4()),
                request_fingerprint="b" * 64,
                feature="education",
                provider="offline",
                model_name="test",
                status="completed",
                reserved_tokens=100,
                prompt_tokens=11,
                completion_tokens=7,
            ),
            AIUsage(
                user_id=another_user.id,
                request_id=str(uuid4()),
                request_fingerprint="c" * 64,
                feature="analysis",
                provider="offline",
                model_name="test",
                status="failed",
                reserved_tokens=200,
            ),
        ]
    )
    db.commit()
    indexed_paper(db, another_user.id)
    failed_job(db, another_user.id)
    response = administrator.get(BASE + "/overview")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["counts"] == {
        "total_users": 2,
        "verified_users": 1,
        "active_sessions": 2,
        "total_papers": 1,
        "total_library_papers": 2,
        "legacy_paper_records": 2,
        "indexed_documents": 1,
        "failed_processing_jobs": 1,
        "active_team_workspaces": 1,
    }
    assert result["ai_usage"] == {
        "requests": 2,
        "prompt_tokens": 11,
        "completion_tokens": 7,
        "reserved_unsettled_tokens": 200,
        "status_counts": {"completed": 1, "failed": 1},
    }
    assert result["health"]["database"] == "ok"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "Private source title" not in response.text
    db.expire_all()
    assert (
        db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.user_id == test_user.id,
                AuditLog.action == "admin.overview.read",
            )
        )
        == 1
    )


def test_paginated_user_directory_contains_only_safe_identity_and_counts(
    administrator, db, test_user, another_user, another_access_token
):
    job_id, _ = failed_job(db, another_user.id)
    response = administrator.get(BASE + "/users?limit=1&offset=1")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2 and body["limit"] == 1 and body["offset"] == 1
    row = body["items"][0]
    assert row["id"] == another_user.id and row["email"] == another_user.email
    assert row["is_admin"] is False and row["saved_papers"] == 1
    assert row["active_sessions"] == 1
    assert not {"hashed_password", "token_jti", "password", "session_id"} & row.keys()
    assert another_access_token not in response.text
    assert "Private source title" not in response.text
    assert administrator.get(BASE + "/users?offset=10000").json()["items"] == []


def test_emergency_session_revocation_is_targeted_atomic_and_audited(
    administrator, db, test_user, another_user, another_access_token
):
    second = issue_test_session(db, another_user)
    response = administrator.post(BASE + f"/users/{another_user.id}/revoke-sessions")
    assert response.status_code == 200, response.text
    assert response.json() == {"user_id": another_user.id, "revoked_sessions": 2}
    assert (
        administrator.post(BASE + f"/users/{another_user.id}/revoke-sessions").json()[
            "revoked_sessions"
        ]
        == 0
    )
    assert administrator.get(BASE + "/overview").status_code == 200
    assert (
        administrator.get(
            "/api/v1/users/me",
            headers={"Authorization": f"Bearer {another_access_token}"},
        ).status_code
        == 401
    )
    assert (
        administrator.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {second}"}
        ).status_code
        == 401
    )
    db.expire_all()
    events = list(
        db.scalars(select(AuditLog).where(AuditLog.action == "admin.sessions.revoked"))
    )
    assert len(events) == 2 and all(row.user_id == test_user.id for row in events)
    assert events[0].resource_id == str(another_user.id)
    assert events[0].details == {"revoked_sessions": 2}


def test_administrator_can_revoke_own_session_and_unknown_target_404(
    administrator, test_user
):
    assert (
        administrator.post(BASE + "/users/2147483647/revoke-sessions").status_code
        == 404
    )
    assert (
        administrator.post(BASE + f"/users/{test_user.id}/revoke-sessions").json()[
            "revoked_sessions"
        ]
        == 1
    )
    assert administrator.get(BASE + "/overview").status_code == 401


def test_audit_log_filters_and_redacts_unstructured_private_context(
    administrator, db, another_user
):
    db.add_all(
        [
            AuditLog(
                user_id=another_user.id,
                action="auth.login.failed",
                resource_type="user",
                resource_id=str(another_user.id),
                ip_address="192.0.2.1",
                details={"token": "PRIVATE_TOKEN", "prompt": "PRIVATE_PROMPT"},
            ),
            AuditLog(
                user_id=another_user.id,
                action="auth.login.failed",
                resource_type="document",
                resource_id="private/storage/source.pdf",
                details={"password": "PRIVATE_PASSWORD"},
            ),
            AuditLog(
                user_id=another_user.id,
                action="unsafe event body",
                resource_type="private path /",
                resource_id="secret",
            ),
        ]
    )
    db.commit()
    response = administrator.get(
        BASE + f"/audit-logs?action=auth.login.failed&user_id={another_user.id}&limit=1"
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total"] == 2 and len(data["items"]) == 1 and data["has_more"] is True
    assert data["items"][0]["resource_id"] is None
    raw = administrator.get(BASE + "/audit-logs").text
    for secret in [
        "PRIVATE_TOKEN",
        "PRIVATE_PROMPT",
        "PRIVATE_PASSWORD",
        "private/storage",
        "192.0.2.1",
    ]:
        assert secret not in raw
    assert '"unrecognized"' in raw
    assert all(
        "details" not in item and "ip_address" not in item
        for item in json.loads(raw)["items"]
    )
    db.expire_all()
    assert (
        db.scalar(
            select(func.count(AuditLog.id)).where(
                AuditLog.action == "admin.audit_logs.viewed"
            )
        )
        == 2
    )


def test_failed_job_list_is_safe_and_requeue_resets_current_job_only(
    administrator, db, another_user
):
    jid, did = failed_job(db, another_user.id)
    dispatcher = AsyncMock()
    administrator.app.state.document_dispatcher = dispatcher
    listing = administrator.get(BASE + "/jobs/failed")
    assert listing.status_code == 200, listing.text
    assert listing.json()["items"][0]["id"] == jid
    assert listing.json()["items"][0]["can_requeue"] is True
    for private in [
        "last_error",
        "storage_key",
        "private-original",
        "Private parser",
        "Secret provider",
    ]:
        assert private not in listing.text
    response = administrator.post(BASE + f"/jobs/{jid}/requeue")
    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == another_user.id
    replacement_id = response.json()["id"]
    assert replacement_id != jid
    assert response.json()["requested_job_id"] == jid
    assert response.json()["document_version"] == 2
    dispatcher.enqueue.assert_awaited_once_with(replacement_id)
    db.expire_all()
    job, document = db.get(ProcessingJob, jid), db.get(Document, did)
    assert job.status == "failed" and job.attempts == 5
    assert job.last_error == "Secret provider text with credentials"
    assert job.completed_at is not None
    replacement = db.get(ProcessingJob, replacement_id)
    assert replacement.status == "queued" and replacement.attempts == 0
    assert replacement.last_error is None and replacement.started_at is None
    assert replacement.completed_at is None and replacement.document_version == 2
    assert (
        document.status == "pending"
        and document.error_message is None
        and document.version == 2
    )
    assert db.scalar(select(func.count(ProcessingJob.id))) == 2
    db.rollback()
    assert administrator.post(BASE + f"/jobs/{jid}/requeue").status_code == 409
    dispatcher.enqueue.assert_awaited_once()
    history = administrator.get(BASE + "/jobs/failed").json()["items"]
    assert len(history) == 1 and history[0]["id"] == jid
    assert history[0]["can_requeue"] is False and history[0]["is_current"] is False
    # A stale queue entry cannot claim/publish the replacement generation.
    db.rollback()
    processor = DocumentProcessor(administrator.app.state.discovery_session_factory)
    administrator.portal.call(processor.process_job, jid, another_user.id)
    db.expire_all()
    assert db.get(Document, did).status == "pending"
    assert db.get(ProcessingJob, replacement_id).status == "queued"
    db.expire_all()
    event = db.scalar(select(AuditLog).where(AuditLog.action == "admin.job.requeued"))
    assert event.details["owner_user_id"] == another_user.id


@pytest.mark.parametrize(
    "job_status,document_status,job_version,document_version",
    [
        ("running", "processing", 1, 1),
        ("queued", "pending", 1, 1),
        ("completed", "completed", 1, 1),
        ("failed", "completed", 1, 1),
        ("failed", "failed", 1, 2),
    ],
)
def test_requeue_rejects_running_completed_or_stale_job(
    administrator,
    db,
    another_user,
    job_status,
    document_status,
    job_version,
    document_version,
):
    jid, _ = failed_job(
        db,
        another_user.id,
        status=job_status,
        document_status=document_status,
        version=job_version,
        document_version=document_version,
    )
    dispatcher = AsyncMock()
    administrator.app.state.document_dispatcher = dispatcher
    response = administrator.post(BASE + f"/jobs/{jid}/requeue")
    assert response.status_code == 409, response.text
    dispatcher.enqueue.assert_not_awaited()


def test_requeue_unknown_and_dispatch_failure_preserve_durable_queue(
    administrator, db, another_user
):
    assert administrator.post(BASE + "/jobs/2147483647/requeue").status_code == 404
    jid, _ = failed_job(db, another_user.id)
    dispatcher = AsyncMock()
    dispatcher.enqueue.side_effect = RuntimeError("PRIVATE_BROKER_SECRET")
    administrator.app.state.document_dispatcher = dispatcher
    response = administrator.post(BASE + f"/jobs/{jid}/requeue")
    assert response.status_code == 200, response.text
    assert "PRIVATE_BROKER_SECRET" not in response.text
    db.expire_all()
    assert db.get(ProcessingJob, jid).status == "failed"
    assert db.get(ProcessingJob, response.json()["id"]).status == "queued"


@pytest.mark.parametrize(
    "path",
    [
        "/users?limit=101",
        "/users?offset=-1",
        "/audit-logs?user_id=2147483648",
        "/audit-logs?action=raw%20body",
        "/jobs/failed?limit=0",
    ],
)
def test_admin_query_bounds(administrator, path):
    assert administrator.get(BASE + path).status_code == 422
