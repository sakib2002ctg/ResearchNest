"""Grant/revoke an existing account's admin role with operator DB credentials."""

import argparse

from sqlalchemy import create_engine, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.models.audit_log import AuditLog
from app.models.session import Session as UserSession
from app.models.user import User


def change_admin(db, user_id, enabled):
    """Caller commits role, session invalidation and audit in one transaction."""
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if user is None:
        raise ValueError("Account not found.")
    changed = user.is_admin != enabled
    user.is_admin = enabled
    now = utc_now()
    revoked = db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == user_id,
            UserSession.is_revoked.is_(False),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        .values(is_revoked=True, revoked_at=now)
    ).rowcount
    db.add(
        AuditLog(
            user_id=None,
            action="admin.role.granted" if enabled else "admin.role.revoked",
            resource_type="user",
            resource_id=str(user_id),
            details={"origin": "operator_cli", "revoked_sessions": revoked},
        )
    )
    return {
        "user_id": user_id,
        "is_admin": enabled,
        "changed": changed,
        "revoked_sessions": revoked,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, required=True)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--grant", action="store_true")
    choice.add_argument("--revoke", action="store_true")
    args = parser.parse_args(argv)
    if not 0 < args.user_id <= 2147483647:
        parser.error("user-id must be a positive database account ID.")
    operation = "GRANT" if args.grant else "REVOKE"
    expected = f"{operation} ADMIN {args.user_id}"
    print(
        "Use an authorized operator connection. "
        "Existing device sessions will be revoked."
    )
    try:
        confirmation = input(f"Type {expected} to continue: ")
    except (EOFError, KeyboardInterrupt):
        print("Canceled; no changes made.")
        return 1
    if confirmation != expected:
        print("Canceled; no changes made.")
        return 1
    url = make_url(settings.DATABASE_URL)
    if url.get_backend_name() != "postgresql":
        parser.error("Use an explicit PostgreSQL operator connection.")
    engine = create_engine(
        url,
        hide_parameters=True,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=5000"},
    )
    try:
        with Session(engine) as db, db.begin():
            result = change_admin(db, args.user_id, args.grant)
        print(
            f"Account {result['user_id']}: admin={result['is_admin']}; "
            f"revoked sessions={result['revoked_sessions']}. Sign in again."
        )
        return 0
    except Exception:
        # Database errors may contain credentials/parameters. Do not print them.
        print("Administrator change failed; the transaction was rolled back.")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
