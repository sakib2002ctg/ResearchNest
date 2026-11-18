from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.database import get_db
from app.dependencies.auth_dependencies import oauth2_scheme
from app.models.session import Session as UserSession
from app.models.user import User
from app.repositories.user_repository import UserRepository


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: UserSession


def get_auth_context(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise credentials_exception from None

    subject, jti, sid = payload.get("sub"), payload.get("jti"), payload.get("sid")
    if not isinstance(subject, str) or not subject.isascii() or not subject.isdecimal():
        raise credentials_exception
    if len(subject) > 10 or not 0 < int(subject) <= 2_147_483_647:
        raise credentials_exception
    if any(not isinstance(value, str) or len(value) != 36 for value in (jti, sid)):
        raise credentials_exception
    repository = UserRepository(db)
    user = repository.get_by_id(int(subject))
    if user is None:
        raise credentials_exception
    session = repository.get_active_session(user.id, jti, sid)
    if session is None:
        raise credentials_exception
    return AuthContext(user=user, session=session)


def get_current_user(context: AuthContext = Depends(get_auth_context)) -> User:
    return context.user
