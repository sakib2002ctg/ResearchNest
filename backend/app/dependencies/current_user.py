from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.database import get_db
from app.dependencies.auth_dependencies import oauth2_scheme
from app.models.user import User
from app.repositories.user_repository import UserRepository


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        email = payload.get("sub")

        if email is None:
            raise credentials_exception

    except ValueError:
        raise credentials_exception

    repository = UserRepository(db)
    user = repository.get_by_email(email)

    if user is None:
        raise credentials_exception

    return user