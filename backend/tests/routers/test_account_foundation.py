from datetime import timedelta
from uuid import uuid4

import pytest
from jose import jwt
from passlib.hash import bcrypt
from sqlalchemy import select

from app.core.config import settings
from app.core.security import decode_access_token
from app.core.time import utc_now
from app.models import (
    AuditLog,
    Profile,
    ResearchPaper,
    Session,
    User,
    UserPreference,
    VerificationToken,
)

AUTH = "/api/v1/auth"
ME = "/api/v1/users/me"


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, credentials, user_agent="ResearchNest tests"):
    response = client.post(
        f"{AUTH}/login", json=credentials, headers={"User-Agent": user_agent}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_registration_and_legacy_login_create_account_state(
    client, db, user_payload, login_payload
):
    response = client.post(f"{AUTH}/register", json=user_payload)
    assert response.status_code == 201
    user = db.get(User, response.json()["id"])
    assert user.hashed_password.startswith("$argon2id$")
    assert user.profile.full_name is None
    assert (
        user.preferences.language == "en"
        and user.preferences.allow_external_ai is False
    )
    user.hashed_password = bcrypt.hash(login_payload["password"])
    db.commit()

    token = login(client, login_payload)
    claims = decode_access_token(token)
    session = db.get(Session, claims["sid"])
    assert claims["sub"] == str(user.id)
    assert session.token_jti == claims["jti"] and session.user_id == user.id
    assert session.is_revoked is False and session.user_agent == "ResearchNest tests"
    assert user.hashed_password.startswith("$argon2id$")
    assert db.scalars(select(AuditLog.action).order_by(AuditLog.id)).all() == [
        "user.register",
        "auth.login.success",
    ]


def test_logout_revokes_only_the_current_session(client, db, test_user, login_payload):
    current = login(client, login_payload)
    other = login(client, login_payload)
    assert client.post(f"{AUTH}/logout", headers=bearer(current)).status_code == 204
    assert client.get(f"{AUTH}/me", headers=bearer(current)).status_code == 401
    assert client.get(f"{AUTH}/me", headers=bearer(other)).status_code == 200
    session = db.get(Session, decode_access_token(current)["sid"])
    assert session.is_revoked and session.revoked_at is not None
    assert (
        db.scalar(select(AuditLog).where(AuditLog.action == "auth.logout")).user_id
        == test_user.id
    )


def test_logout_all_and_session_list_are_tenant_scoped(
    client, db, test_user, another_access_token, login_payload
):
    first = login(client, login_payload)
    second = login(client, login_payload)
    first_claims, second_claims = map(decode_access_token, (first, second))
    foreign_id = decode_access_token(another_access_token)["sid"]
    db.add(
        Session(
            user_id=test_user.id,
            token_jti=str(uuid4()),
            expires_at=utc_now() - timedelta(minutes=1),
        )
    )
    db.commit()

    response = client.get(f"{ME}/sessions", headers=bearer(first))
    assert response.status_code == 200
    sessions = response.json()
    assert {row["id"] for row in sessions} == {
        first_claims["sid"],
        second_claims["sid"],
    }
    assert all("token_jti" not in row for row in sessions)
    assert client.post(f"{AUTH}/logout-all", headers=bearer(first)).status_code == 204
    for token in (first, second):
        assert client.get(ME, headers=bearer(token)).status_code == 401
    assert client.get(ME, headers=bearer(another_access_token)).status_code == 200
    assert not db.get(Session, foreign_id).is_revoked
    assert db.scalar(select(AuditLog).where(AuditLog.action == "auth.logout_all"))


@pytest.mark.parametrize(
    "case",
    [
        "expired_session",
        "wrong_subject",
        "missing_session",
        "no_jti",
        "no_sid",
        "bad_audience",
    ],
)
def test_requests_require_a_valid_matching_session(
    client, db, access_token, another_user, case
):
    claims = decode_access_token(access_token)
    if case == "expired_session":
        db.get(Session, claims["sid"]).expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    elif case == "wrong_subject":
        claims["sub"] = str(another_user.id)
    elif case == "missing_session":
        claims["jti"] = str(uuid4())
    elif case == "no_jti":
        claims.pop("jti")
    elif case == "no_sid":
        claims.pop("sid")
    elif case == "bad_audience":
        claims["aud"] = "different-client"
    token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    response = client.get(ME, headers=bearer(token))
    assert (
        response.status_code == 401 and response.headers["WWW-Authenticate"] == "Bearer"
    )


def test_profile_and_preferences_are_private_and_validate_input(
    client, access_token, another_access_token, test_user
):
    headers = bearer(access_token)
    profile_url, preferences_url = f"{ME}/profile", f"{ME}/preferences"
    assert client.get(profile_url, headers=headers).json()["full_name"] is None
    response = client.put(
        profile_url,
        headers=headers,
        json={"full_name": "বাংলা নাম", "avatar_url": "https://example.com/avatar"},
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == test_user.id
    assert response.json()["full_name"] == "বাংলা নাম"
    assert (
        client.put(
            profile_url, headers=headers, json={"user_id": test_user.id + 1}
        ).status_code
        == 422
    )
    assert (
        client.get(profile_url, headers=bearer(another_access_token)).json()[
            "full_name"
        ]
        is None
    )

    defaults = client.get(preferences_url, headers=headers).json()
    assert (
        defaults["language"],
        defaults["theme"],
        defaults["privacy_default"],
        defaults["allow_external_ai"],
    ) == ("en", "system", "private", False)
    response = client.put(
        preferences_url,
        headers=headers,
        json={"language": "bn", "allow_external_ai": True},
    )
    assert response.status_code == 200 and response.json()["allow_external_ai"] is True
    assert response.json()["language"] == "bn"
    for values in (
        {"language": "fr"},
        {"allow_external_ai": "true"},
        {"allow_external_ai": None},
    ):
        assert (
            client.put(preferences_url, headers=headers, json=values).status_code == 422
        )
    assert (
        client.put(preferences_url, headers=headers, json={"theme": "dark"}).json()[
            "language"
        ]
        == "bn"
    )
    other = client.get(preferences_url, headers=bearer(another_access_token)).json()
    assert other["language"] == "en" and other["allow_external_ai"] is False


def test_activity_is_scoped_and_contains_only_safe_metadata(
    client, db, test_user, another_access_token, login_payload
):
    secret = "wrong-password-for-audit"
    unknown = "unknown-audit@example.com"
    for email in (login_payload["email"], unknown):
        assert (
            client.post(
                f"{AUTH}/login", json={"email": email, "password": secret}
            ).status_code
            == 401
        )
    token = login(client, login_payload)
    client.put(f"{ME}/preferences", headers=bearer(token), json={"language": "bn"})
    response = client.get(f"{ME}/activity", headers=bearer(token))
    assert [row["action"] for row in response.json()] == [
        "user.preferences.update",
        "auth.login.success",
        "auth.login.failed",
    ]
    assert response.json()[0]["details"] == {"fields": ["language"]}
    assert (
        client.get(f"{ME}/activity?limit=1", headers=bearer(token)).json()
        == response.json()[:1]
    )
    assert (
        client.get(f"{ME}/activity", headers=bearer(another_access_token)).json() == []
    )
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.action == "auth.login.failed")
        .order_by(AuditLog.id)
    ).all()
    assert [row.user_id for row in rows] == [test_user.id, None]
    assert all(row.details is None and row.resource_id is None for row in rows)
    assert all(value not in response.text for value in (secret, unknown, token))


def test_account_deletion_cascades_private_data_and_retains_audit(
    client, db, user_payload, login_payload, another_access_token
):
    user_id = client.post(f"{AUTH}/register", json=user_payload).json()["id"]
    token = login(client, login_payload)
    assert (
        client.post(
            "/api/v1/papers/", headers=bearer(token), json={"title": "Private"}
        ).status_code
        == 200
    )
    db.add(
        VerificationToken(
            user_id=user_id,
            token_hash="f" * 64,
            purpose="email_verification",
            expires_at=utc_now() + timedelta(hours=1),
        )
    )
    db.commit()
    assert client.delete(ME, headers=bearer(token)).status_code == 204
    assert client.get(ME, headers=bearer(token)).status_code == 401
    assert client.get(ME, headers=bearer(another_access_token)).status_code == 200
    assert db.get(User, user_id) is None
    for model in (Profile, UserPreference, Session, ResearchPaper, VerificationToken):
        assert (
            db.scalar(
                select(model).where(model.user_id == user_id)
                if model is not ResearchPaper
                else select(model).where(model.owner_id == user_id)
            )
            is None
        )
    log = db.scalar(select(AuditLog).where(AuditLog.action == "user.account.delete"))
    assert log.user_id is None and log.resource_id == str(user_id)
    log.action = "unauthorized-rewrite"
    with pytest.raises(ValueError, match="append-only"):
        db.flush()
    db.rollback()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/profile"),
        ("PUT", "/profile"),
        ("GET", "/preferences"),
        ("PUT", "/preferences"),
        ("GET", "/sessions"),
        ("GET", "/activity"),
        ("DELETE", ""),
    ],
)
def test_account_routes_require_authentication(client, method, path):
    assert client.request(method, f"{ME}{path}", json={}).status_code == 401
