import hashlib
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import decode_access_token, verify_password
from app.core.time import utc_now
from app.models import AuditLog, Session, User, VerificationToken
from app.models.library import (
    Annotation,
    Collection,
    CollectionPaper,
    Document,
    PaperTag,
    Tag,
)
from app.models.paper import UserPaper
from app.repositories.paper_repository import PaperRepository
from app.schemas.research_paper import ResearchPaperCreate

AUTH = "/api/v1/auth"
ME = "/api/v1/users/me"


def headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_email_verification_request_replaces_old_token_and_confirm_is_single_use(
    client, db, authenticated_client, test_user, monkeypatch
):
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "APP_ENV", "test")
    first = authenticated_client.post(f"{AUTH}/verify-email/request").json()[
        "debug_token"
    ]
    second = authenticated_client.post(f"{AUTH}/verify-email/request").json()[
        "debug_token"
    ]
    first_hash = hashlib.sha256(first.encode()).hexdigest()
    second_hash = hashlib.sha256(second.encode()).hexdigest()
    old = db.scalar(
        select(VerificationToken).where(VerificationToken.token_hash == first_hash)
    )
    active = db.scalar(
        select(VerificationToken).where(VerificationToken.token_hash == second_hash)
    )
    assert first != second and old.used_at is not None
    assert active.used_at is None and active.purpose == "email_verification"
    assert active.expires_at - active.created_at > timedelta(hours=23)

    assert (
        client.post(f"{AUTH}/verify-email/confirm", json={"token": first}).status_code
        == 400
    )
    response = client.post(f"{AUTH}/verify-email/confirm", json={"token": second})
    assert response.status_code == 200
    assert db.get(User, test_user.id).is_verified is True
    assert active.used_at is not None
    assert (
        client.post(f"{AUTH}/verify-email/confirm", json={"token": second}).status_code
        == 400
    )
    actions = db.scalars(
        select(AuditLog.action).where(AuditLog.user_id == test_user.id)
    ).all()
    assert actions[-1] == "auth.email_verification.confirmed"
    assert first_hash != first and second_hash != second


@pytest.mark.parametrize("bad_kind", ["expired", "wrong_purpose", "used"])
def test_email_verification_rejects_expired_wrong_purpose_and_reused_tokens(
    client, db, test_user, bad_kind
):
    value = f"test-verification-token-{bad_kind}-" + "x" * 32
    row = VerificationToken(
        user_id=test_user.id,
        token_hash=hashlib.sha256(value.encode()).hexdigest(),
        purpose=(
            "password_reset" if bad_kind == "wrong_purpose" else "email_verification"
        ),
        expires_at=(
            utc_now() - timedelta(seconds=1)
            if bad_kind == "expired"
            else utc_now() + timedelta(hours=1)
        ),
        used_at=utc_now() if bad_kind == "used" else None,
    )
    db.add(row)
    db.commit()
    response = client.post(f"{AUTH}/verify-email/confirm", json={"token": value})
    assert response.status_code == 400
    assert db.get(User, test_user.id).is_verified is False


def test_reset_request_is_generic_for_known_and_unknown_email(
    client, user_payload, monkeypatch
):
    monkeypatch.setattr(settings, "DEBUG", False)
    assert client.post(f"{AUTH}/register", json=user_payload).status_code == 201
    known = client.post(
        f"{AUTH}/password-reset/request", json={"email": user_payload["email"]}
    )
    unknown = client.post(
        f"{AUTH}/password-reset/request", json={"email": "nobody@example.com"}
    )
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert known.json() == {
        "message": "If the account exists, password reset instructions will be sent.",
    }


def test_password_reset_is_single_use_hashes_password_and_revokes_all_sessions(
    client, db, access_token, another_access_token, login_payload, monkeypatch
):
    monkeypatch.setattr(settings, "DEBUG", True)
    deliveries = []
    monkeypatch.setattr(
        "app.routers.auth.send_identity_token",
        lambda *values: deliveries.append(values),
    )
    other_device = client.post(f"{AUTH}/login", json=login_payload).json()[
        "access_token"
    ]
    session_ids = {
        decode_access_token(value)["sid"] for value in (access_token, other_device)
    }
    reset_response = client.post(
        f"{AUTH}/password-reset/request", json={"email": login_payload["email"]}
    )
    assert reset_response.status_code == 200
    assert "debug_token" not in reset_response.json()
    assert len(deliveries) == 1
    recipient, token, purpose = deliveries[0]
    assert (recipient, purpose) == (login_payload["email"], "password_reset")
    stored = db.scalar(
        select(VerificationToken).where(
            VerificationToken.token_hash == hashlib.sha256(token.encode()).hexdigest()
        )
    )
    assert stored is not None and stored.token_hash != token
    assert (
        timedelta(minutes=15)
        <= stored.expires_at - stored.created_at
        <= timedelta(minutes=30)
    )

    password = "new-strong-password-123"
    response = client.post(
        f"{AUTH}/password-reset/confirm",
        json={"token": token, "new_password": password},
    )
    assert response.status_code == 200
    assert all(db.get(Session, session_id).is_revoked for session_id in session_ids)
    assert (
        client.post(
            f"{AUTH}/password-reset/confirm",
            json={"token": token, "new_password": "another-new-password"},
        ).status_code
        == 400
    )
    assert client.get(ME, headers=headers(access_token)).status_code == 401
    assert client.get(ME, headers=headers(other_device)).status_code == 401
    assert client.get(ME, headers=headers(another_access_token)).status_code == 200
    user = db.scalar(select(User).where(User.email == login_payload["email"]))
    assert user.hashed_password.startswith("$argon2id$")
    assert verify_password(password, user.hashed_password)
    assert db.scalar(
        select(AuditLog).where(AuditLog.action == "auth.password_reset.completed")
    )
    assert (
        client.post(
            f"{AUTH}/login",
            json={"email": login_payload["email"], "password": password},
        ).status_code
        == 200
    )


def test_password_change_revokes_other_sessions_but_keeps_current(
    client, db, access_token, login_payload
):
    other = client.post(f"{AUTH}/login", json=login_payload).json()["access_token"]
    current_claims = decode_access_token(access_token)
    other_claims = decode_access_token(other)
    response = client.post(
        f"{AUTH}/password-change",
        headers=headers(access_token),
        json={
            "current_password": login_payload["password"],
            "new_password": "changed-password-123",
        },
    )
    assert response.status_code == 200
    assert not db.get(Session, current_claims["sid"]).is_revoked
    assert db.get(Session, other_claims["sid"]).is_revoked
    assert client.get(ME, headers=headers(access_token)).status_code == 200
    assert client.get(ME, headers=headers(other)).status_code == 401
    assert db.scalar(select(AuditLog).where(AuditLog.action == "auth.password_change"))
    assert (
        client.post(
            f"{AUTH}/login",
            json={"email": login_payload["email"], "password": "changed-password-123"},
        ).status_code
        == 200
    )
    assert client.post(f"{AUTH}/login", json=login_payload).status_code == 401


def test_password_change_rejects_wrong_current_password(client, access_token):
    response = client.post(
        f"{AUTH}/password-change",
        headers=headers(access_token),
        json={
            "current_password": "incorrect-password",
            "new_password": "changed-password-123",
        },
    )
    assert response.status_code == 400
    assert client.get(ME, headers=headers(access_token)).status_code == 200


def test_individual_session_revocation_is_owner_scoped_and_audited(
    client, db, access_token, another_access_token, test_user
):
    own_id = decode_access_token(access_token)["sid"]
    foreign_id = decode_access_token(another_access_token)["sid"]
    assert (
        client.delete(
            f"{ME}/sessions/{foreign_id}", headers=headers(access_token)
        ).status_code
        == 404
    )
    assert not db.get(Session, foreign_id).is_revoked
    assert (
        client.delete(
            f"{ME}/sessions/{own_id}", headers=headers(access_token)
        ).status_code
        == 204
    )
    assert client.get(ME, headers=headers(access_token)).status_code == 401
    audit = db.scalar(
        select(AuditLog).where(
            AuditLog.action == "auth.session.revoked",
            AuditLog.user_id == test_user.id,
        )
    )
    assert audit.resource_id == own_id
    assert (
        client.delete(
            f"{ME}/sessions/{own_id}", headers=headers(another_access_token)
        ).status_code
        == 404
    )


def test_export_is_allowlisted_and_contains_only_callers_data(
    client, db, access_token, another_access_token, test_user, another_user
):
    own = PaperRepository(db).create_paper(
        ResearchPaperCreate(title="Private export A"), owner_id=test_user.id
    )
    foreign = PaperRepository(db).create_paper(
        ResearchPaperCreate(title="Private export B"), owner_id=another_user.id
    )
    own_link = (
        db.query(UserPaper)
        .filter_by(user_id=test_user.id, legacy_paper_id=own.id)
        .one()
    )
    foreign_link = (
        db.query(UserPaper)
        .filter_by(user_id=another_user.id, legacy_paper_id=foreign.id)
        .one()
    )
    own_collection = Collection(user_id=test_user.id, name="Private collection")
    foreign_collection = Collection(user_id=another_user.id, name="Foreign collection")
    own_tag = Tag(user_id=test_user.id, name="Private tag", color="#168049")
    foreign_tag = Tag(user_id=another_user.id, name="Foreign tag")
    db.add_all([own_collection, foreign_collection, own_tag, foreign_tag])
    db.flush()
    db.add_all(
        [
            CollectionPaper(
                user_id=test_user.id,
                collection_id=own_collection.id,
                user_paper_id=own_link.id,
            ),
            CollectionPaper(
                user_id=another_user.id,
                collection_id=foreign_collection.id,
                user_paper_id=foreign_link.id,
            ),
            PaperTag(
                user_id=test_user.id, tag_id=own_tag.id, user_paper_id=own_link.id
            ),
            PaperTag(
                user_id=another_user.id,
                tag_id=foreign_tag.id,
                user_paper_id=foreign_link.id,
            ),
            Annotation(
                user_id=test_user.id,
                user_paper_id=own_link.id,
                type="note",
                content="Private page note",
                page_number=2,
            ),
            Annotation(
                user_id=another_user.id,
                user_paper_id=foreign_link.id,
                type="note",
                content="Foreign note",
            ),
            Document(
                user_id=test_user.id,
                user_paper_id=own_link.id,
                storage_key="private-storage-key.pdf",
                original_filename="my-paper.pdf",
                size_bytes=1234,
                sha256="f" * 64,
                page_count=7,
            ),
            Document(
                user_id=another_user.id,
                user_paper_id=foreign_link.id,
                storage_key="foreign-storage-key.pdf",
                original_filename="other.pdf",
                size_bytes=4321,
                sha256="e" * 64,
                page_count=8,
            ),
        ]
    )
    db.commit()
    response = client.get(f"{ME}/export", headers=headers(access_token))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    data = response.json()
    assert data["account"]["id"] == test_user.id
    assert {paper["id"] for paper in data["papers"]} == {own.id}
    assert data["collections"][0]["name"] == "Private collection"
    assert data["tags"][0]["name"] == "Private tag"
    assert len(data["library_items"]) == 1
    item = data["library_items"][0]
    assert item["user_paper_id"] == own_link.id
    assert item["collection_ids"] == [own_collection.id]
    assert item["tag_ids"] == [own_tag.id]
    assert item["annotations"][0]["content"] == "Private page note"
    assert item["document"]["original_filename"] == "my-paper.pdf"
    assert "storage_key" not in response.text
    assert "private-storage-key" not in response.text
    assert "foreign-storage-key" not in response.text
    assert "Foreign collection" not in response.text
    assert "Foreign tag" not in response.text
    assert "Foreign note" not in response.text
    assert all(paper["id"] != foreign.id for paper in data["papers"])
    assert data["profile"]["user_id"] == data["preferences"]["user_id"] == test_user.id
    assert {session["id"] for session in data["active_sessions"]} == {
        decode_access_token(access_token)["sid"]
    }
    assert all(row["user_id"] == test_user.id for row in data["audit_logs"])
    assert data["audit_logs"][0]["action"] == "user.data.exported"
    for field in ("hashed_password", "token_jti", "token_hash", "verification_tokens"):
        assert field not in response.text
    assert (
        client.get(f"{ME}/export", headers=headers(another_access_token)).json()[
            "account"
        ]["id"]
        == another_user.id
    )


def test_dashboard_is_aggregated_and_tenant_scoped(
    client, db, access_token, another_access_token, test_user, another_user
):
    repository = PaperRepository(db)
    papers = []
    base = utc_now()
    for index in range(7):
        paper = repository.create_paper(
            ResearchPaperCreate(title=f"Dashboard A {index}"),
            owner_id=test_user.id,
        )
        paper.created_at = base + timedelta(seconds=index)
        papers.append(paper)
    foreign = repository.create_paper(
        ResearchPaperCreate(title="Dashboard B private"), owner_id=another_user.id
    )
    db.commit()
    for index in range(7):
        db.add(
            AuditLog(
                user_id=test_user.id,
                action=f"own.{index}",
                created_at=base + timedelta(seconds=index),
            )
        )
    db.add(
        AuditLog(
            user_id=another_user.id,
            action="foreign",
            created_at=base + timedelta(seconds=20),
        )
    )
    db.commit()
    response = client.get(f"{ME}/dashboard", headers=headers(access_token))
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["id"] == test_user.id
    assert data["verification_status"] is False
    assert data["language"] == "en" and data["privacy_default"] == "private"
    assert data["saved_papers_count"] == 7
    assert [paper["id"] for paper in data["recent_papers"]] == [
        paper.id for paper in reversed(papers[-5:])
    ]
    assert all(paper["id"] != foreign.id for paper in data["recent_papers"])
    assert data["active_sessions_count"] == 1
    assert [event["action"] for event in data["recent_activity"]] == [
        f"own.{index}" for index in range(6, 1, -1)
    ]
    other = client.get(f"{ME}/dashboard", headers=headers(another_access_token)).json()
    assert other["user"]["id"] == another_user.id
    assert other["saved_papers_count"] == 1


@pytest.mark.parametrize("state", ["expired", "used", "wrong_purpose", "unknown"])
def test_reset_rejects_invalid_tokens_without_mutating_password(
    state, client, db, test_user, access_token
):
    raw = "invalid-reset-case-" + state + "x" * 32
    old_hash = test_user.hashed_password
    if state != "unknown":
        db.add(
            VerificationToken(
                user_id=test_user.id,
                token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                purpose=(
                    "email_verification"
                    if state == "wrong_purpose"
                    else "password_reset"
                ),
                expires_at=utc_now()
                + timedelta(minutes=-1 if state == "expired" else 20),
                used_at=utc_now() if state == "used" else None,
            )
        )
        db.commit()
    response = client.post(
        f"{AUTH}/password-reset/confirm",
        json={"token": raw, "new_password": "rejected-password-123"},
    )
    assert response.status_code == 400
    db.refresh(test_user)
    assert test_user.hashed_password == old_hash
    assert client.get(ME, headers=headers(access_token)).status_code == 200
    assert not db.scalar(
        select(AuditLog).where(AuditLog.action == "auth.password_reset.completed")
    )


def test_reissuing_reset_replaces_prior_token_and_password_change_cancels_reset(
    client, db, access_token, login_payload, monkeypatch
):
    deliveries = []
    monkeypatch.setattr(
        "app.routers.auth.send_identity_token",
        lambda *values: deliveries.append(values),
    )
    for _ in range(2):
        assert (
            client.post(
                f"{AUTH}/password-reset/request", json={"email": login_payload["email"]}
            ).status_code
            == 200
        )
    first, second = (values[1] for values in deliveries)
    assert first != second
    assert (
        client.post(
            f"{AUTH}/password-reset/confirm",
            json={"token": first, "new_password": "rejected-password-123"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"{AUTH}/password-change",
            headers=headers(access_token),
            json={
                "current_password": login_payload["password"],
                "new_password": "replacement-password-123",
            },
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"{AUTH}/password-reset/confirm",
            json={"token": second, "new_password": "rejected-password-123"},
        ).status_code
        == 400
    )
    assert client.get(ME, headers=headers(access_token)).status_code == 200


@pytest.mark.parametrize(
    "environment,debug,expected",
    [
        ("production", True, False),
        ("development", False, False),
        ("test", True, True),
    ],
)
def test_verification_token_visibility_is_explicitly_gated(
    client, access_token, monkeypatch, environment, debug, expected
):
    monkeypatch.setattr(settings, "APP_ENV", environment)
    monkeypatch.setattr(settings, "DEBUG", debug)
    result = client.post(f"{AUTH}/verify-email/request", headers=headers(access_token))
    assert result.status_code == 200
    assert ("debug_token" in result.json()) is expected
    assert result.headers["cache-control"] == "private, no-store"


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/v1/auth/verify-email/request", "POST"),
        ("/api/v1/auth/password-change", "POST"),
        ("/api/v1/users/me/sessions/example", "DELETE"),
        ("/api/v1/users/me/export", "GET"),
        ("/api/v1/users/me/dashboard", "GET"),
    ],
)
def test_new_private_routes_require_authentication(client, path, method):
    assert (
        client.request(
            method,
            path,
            json={"current_password": "password123", "new_password": "password456"},
        ).status_code
        == 401
    )


def test_reset_delivery_failure_has_the_same_public_response(
    client, test_user, login_payload, monkeypatch, caplog
):
    from app.core.identity_email import IdentityEmailDeliveryError

    def failing_mail(*args):
        raise IdentityEmailDeliveryError("mail secret must never reach a log")

    monkeypatch.setattr("app.routers.auth.send_identity_token", failing_mail)
    existing = client.post(
        f"{AUTH}/password-reset/request", json={"email": login_payload["email"]}
    )
    unknown = client.post(
        f"{AUTH}/password-reset/request", json={"email": "not-registered@example.com"}
    )
    assert existing.status_code == unknown.status_code == 200
    assert existing.json() == unknown.json()
    assert "mail secret" not in caplog.text


def test_validation_errors_do_not_reflect_passwords_or_recovery_tokens(client):
    token = "sensitive-token-" * 12
    password = "sensitive-password-" * 12
    response = client.post(
        f"{AUTH}/password-reset/confirm",
        json={
            "token": token,
            "new_password": password,
        },
    )
    assert response.status_code == 422
    assert token not in response.text and password not in response.text
    assert all("input" not in error for error in response.json()["detail"])


def test_reset_rate_limit_preserves_generic_response_and_last_token(
    client, db, test_user, login_payload, monkeypatch
):
    monkeypatch.setattr(settings, "IDENTITY_REQUEST_LIMIT", 2)
    deliveries = []
    monkeypatch.setattr(
        "app.routers.auth.send_identity_token",
        lambda *values: deliveries.append(values),
    )
    responses = [
        client.post(
            f"{AUTH}/password-reset/request", json={"email": login_payload["email"]}
        )
        for _ in range(4)
    ]
    assert all(response.status_code == 200 for response in responses)
    assert all(response.json() == responses[0].json() for response in responses)
    assert len(deliveries) == 2
    rows = db.scalars(
        select(VerificationToken).where(
            VerificationToken.user_id == test_user.id,
            VerificationToken.purpose == "password_reset",
        )
    ).all()
    assert len(rows) == 2 and sum(row.used_at is None for row in rows) == 1
    latest = deliveries[-1][1]
    assert (
        client.post(
            f"{AUTH}/password-reset/confirm",
            json={
                "token": latest,
                "new_password": "new-limited-password-123",
            },
        ).status_code
        == 200
    )
