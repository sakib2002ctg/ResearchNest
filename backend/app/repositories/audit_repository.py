from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def add_audit(
    db: Session,
    action: str,
    user_id: int | None,
    ip_address: str | None = None,
    resource_type: str = "user",
    resource_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Only internal, allowlisted event metadata belongs here, never request bodies."""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            ip_address=ip_address,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
    )
