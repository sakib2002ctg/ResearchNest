"""Concurrency checks against a dedicated, disposable PostgreSQL database."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, func, inspect, select, text
from sqlalchemy.orm import Session as DatabaseSession
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.core.security import hash_password, verify_password
from app.core.time import utc_now
from app.models import AuditLog, Session, User, VerificationToken
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserCreate
from app.services.user_service import UserService, hash_verification_token


@pytest.fixture(scope="module")
def identity_database():
    url = os.getenv("TEST_IDENTITY_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set TEST_IDENTITY_DATABASE_URL to a disposable empty PostgreSQL DB"
        )

    engine = create_engine(url)
    assert engine.dialect.name == "postgresql"
    assert not inspect(engine).get_table_names(), "Identity test DB must be empty"
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    try:
        command.upgrade(config, "head")
        yield engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")
        with engine.begin() as connection:
            assert (
                connection.execute(
                    text("SELECT count(*) FROM alembic_version")
                ).scalar_one()
                == 0
            )
            connection.execute(text("DROP TABLE alembic_version"))
        engine.dispose()


@pytest.fixture
def identity_user(identity_database):
    suffix = uuid4().hex
    email = f"identity-{suffix}@example.com"
    with DatabaseSession(identity_database) as db:
        user = UserService(UserRepository(db)).create_user(
            UserCreate(
                username=f"identity-{suffix}", email=email, password="password123"
            )
        )
        return user.id, email


def run_at_account_lock(engine, operation):
    """Ensure both workers reach the user lock before either can complete."""
    gate = Barrier(2)
    database_sessions = sessionmaker(bind=engine)

    class SimultaneousRepository(UserRepository):
        def lock_user(self, user_id):
            gate.wait(timeout=15)
            return super().lock_user(user_id)

    def worker():
        with database_sessions() as db:
            service = UserService(SimultaneousRepository(db))
            return operation(service)

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(worker) for _ in range(2)]
        return [future.result(timeout=30) for future in futures]


@pytest.mark.parametrize("purpose", ["email_verification", "password_reset"])
def test_concurrent_confirmations_are_single_use(
    identity_database, identity_user, purpose
):
    user_id, email = identity_user
    with DatabaseSession(identity_database) as db:
        service = UserService(UserRepository(db))
        if purpose == "email_verification":
            token = service.issue_email_verification(user_id, None)
        else:
            token = service.request_password_reset(email, None)
        assert token is not None
        old_session = Session(
            user_id=user_id,
            token_jti=str(uuid4()),
            expires_at=utc_now() + timedelta(minutes=30),
        )
        db.add(old_session)
        db.commit()
        old_session_id = old_session.id

    def confirm(service):
        try:
            if purpose == "email_verification":
                service.confirm_email_verification(token, None)
            else:
                service.confirm_password_reset(token, "updated-password123", None)
            return True
        except ValueError as exc:
            assert str(exc).startswith("Invalid or expired")
            return False

    assert sorted(run_at_account_lock(identity_database, confirm)) == [False, True]
    action = (
        "auth.email_verification.confirmed"
        if purpose == "email_verification"
        else "auth.password_reset.completed"
    )
    with DatabaseSession(identity_database) as db:
        stored = db.scalar(
            select(VerificationToken).where(
                VerificationToken.token_hash == hash_verification_token(token)
            )
        )
        assert stored.used_at is not None
        assert (
            db.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.user_id == user_id, AuditLog.action == action
                )
            )
            == 1
        )
        user = db.get(User, user_id)
        if purpose == "email_verification":
            assert user.is_verified
        else:
            assert verify_password("updated-password123", user.hashed_password)
            assert db.get(Session, old_session_id).is_revoked


@pytest.mark.parametrize("purpose", ["email_verification", "password_reset"])
def test_concurrent_issuance_leaves_only_one_usable_token(
    identity_database, identity_user, purpose
):
    user_id, email = identity_user

    def issue(service):
        if purpose == "email_verification":
            return service.issue_email_verification(user_id, None)
        return service.request_password_reset(email, None)

    issued_tokens = run_at_account_lock(identity_database, issue)
    plaintext = [token for token in issued_tokens if token is not None]
    assert plaintext
    assert len(plaintext) == len(set(plaintext))
    with DatabaseSession(identity_database) as db:
        unused = db.scalars(
            select(VerificationToken).where(
                VerificationToken.user_id == user_id,
                VerificationToken.purpose == purpose,
                VerificationToken.used_at.is_(None),
                VerificationToken.expires_at > utc_now(),
            )
        ).all()
        assert len(unused) == 1
        assert unused[0].token_hash in {
            hash_verification_token(token) for token in plaintext
        }


def test_stale_login_cannot_create_session_after_password_replacement(
    identity_database, identity_user
):
    user_id, _ = identity_user
    with DatabaseSession(identity_database) as stale_db:
        stale_repository = UserRepository(stale_db)
        user = stale_repository.get_by_id(user_id)
        observed_hash = user.hashed_password
        assert verify_password("password123", observed_hash)

        with DatabaseSession(identity_database) as replacement_db:
            replacement_repository = UserRepository(replacement_db)
            locked_user = replacement_repository.lock_user(user_id)
            replacement_repository.replace_password(
                locked_user,
                hash_password("replacement-password123"),
                "auth.password_reset.completed",
                None,
            )

        rejected_session = Session(
            id=str(uuid4()),
            user_id=user_id,
            token_jti=str(uuid4()),
            expires_at=utc_now() + timedelta(minutes=30),
        )
        assert not stale_repository.start_session(
            user, rejected_session, expected_hash=observed_hash
        )
        stale_db.rollback()

    with DatabaseSession(identity_database) as db:
        assert db.get(Session, rejected_session.id) is None
        assert (
            db.scalar(
                select(func.count(AuditLog.id)).where(
                    AuditLog.user_id == user_id, AuditLog.action == "auth.login.success"
                )
            )
            == 0
        )
