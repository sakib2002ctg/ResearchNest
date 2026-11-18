from datetime import datetime, timedelta
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from jose import JWTError, jwt
from passlib.hash import bcrypt

from app.core.config import settings
from app.core.time import utc_now

password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plain-text password."""
    return password_hasher.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its hash."""
    try:
        if bcrypt.identify(hashed_password):
            return bcrypt.verify(plain_password, hashed_password)
        return password_hasher.verify(hashed_password, plain_password)
    except (ValueError, TypeError, InvalidHashError, VerificationError):
        return False


def password_needs_rehash(hashed_password: str) -> bool:
    return bcrypt.identify(hashed_password) or password_hasher.check_needs_rehash(
        hashed_password
    )


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
    *,
    issued_at: datetime | None = None,
) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()

    issued_at = issued_at if issued_at is not None else utc_now()
    expire = issued_at + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update(
        {
            "exp": expire,
            "iat": issued_at,
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        }
    )
    to_encode.setdefault("jti", str(uuid4()))

    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={
                "require_exp": True,
                "require_sub": True,
                "require_jti": True,
                "require_iat": True,
                "require_iss": True,
                "require_aud": True,
            },
        )
        return payload
    except JWTError:
        raise ValueError("Invalid or expired token.")
