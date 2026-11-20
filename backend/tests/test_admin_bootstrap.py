from sqlalchemy import select

from app.cli import admin
from app.models.audit_log import AuditLog
from app.models.session import Session


def test_operator_role_changes_are_audited_and_revoke_existing_sessions(
    db, test_user, access_token
):
    assert test_user.is_admin is False
    result = admin.change_admin(db, test_user.id, True)
    db.commit()
    assert result["changed"] is True and result["revoked_sessions"] == 1
    assert test_user.is_admin is True
    assert db.scalar(select(Session).where(Session.user_id == test_user.id)).is_revoked
    repeated = admin.change_admin(db, test_user.id, True)
    assert repeated["changed"] is False and repeated["revoked_sessions"] == 0
    db.commit()
    admin.change_admin(db, test_user.id, False)
    db.commit()
    assert test_user.is_admin is False
    events = list(db.scalars(select(AuditLog).order_by(AuditLog.id)))
    assert [row.action for row in events] == [
        "admin.role.granted",
        "admin.role.granted",
        "admin.role.revoked",
    ]
    assert all(
        row.user_id is None and row.details["origin"] == "operator_cli"
        for row in events
    )


def test_operator_cancel_never_connects_or_changes_roles(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda _: "cancel")

    def forbidden(*args, **kwargs):
        raise AssertionError("Cancellation must not open a database connection")

    monkeypatch.setattr(admin, "create_engine", forbidden)
    assert admin.main(["--user-id", "42", "--grant"]) == 1
    assert "Canceled" in capsys.readouterr().out
