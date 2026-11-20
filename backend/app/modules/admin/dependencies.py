from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.dependencies.current_user import AuthContext, get_auth_context
from app.models.audit_log import AuditLog
from app.models.user import User


@dataclass(frozen=True)
class AdminPrincipal:
    user_id: int
    session_id: str
    token_jti: str


def require_admin_user(
    request: Request,
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> AdminPrincipal:
    """Check the stored role, never a token claim or request-supplied flag."""
    principal = AdminPrincipal(
        context.user.id, context.session.id, context.session.token_jti
    )
    try:
        # A scalar query avoids a stale role on an already-loaded ORM User.
        if not db.scalar(select(User.is_admin).where(User.id == principal.user_id)):
            route = getattr(request.scope.get("route"), "path", "/api/v1/admin")
            db.add(
                AuditLog(
                    user_id=principal.user_id,
                    action="admin.access.denied",
                    resource_type="admin",
                    details={"method": request.method, "route": route},
                )
            )
            db.commit()
            raise HTTPException(403, "Administrative access required.")
        return principal
    finally:
        db.rollback()  # release the authentication connection before async work


Admin = Annotated[AdminPrincipal, Depends(require_admin_user)]
