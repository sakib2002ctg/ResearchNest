import hashlib
import secrets
from datetime import timedelta
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.core.time import utc_now
from app.models.profile import Profile
from app.models.session import Session
from app.models.user import User
from app.models.user_preference import UserPreference
from app.repositories.user_repository import UserRepository
from app.schemas.user import Token, UserCreate

DUMMY_HASH = hash_password("unused-login-timing-placeholder")


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def create_user(self, user_data: UserCreate, ip_address: str | None = None) -> User:
        if self.repository.get_by_email(user_data.email):
            raise ValueError("Email already exists.")

        if self.repository.get_by_username(user_data.username):
            raise ValueError("Username already exists.")

        user = User(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hash_password(user_data.password),
            profile=Profile(),
            preferences=UserPreference(),
        )

        try:
            return self.repository.create(user, ip_address)
        except IntegrityError:
            self.repository.db.rollback()
            raise ValueError("Email or username already exists.") from None

    def authenticate_user(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Token:
        user = self.repository.get_by_email(email)

        password_hash = user.hashed_password if user else DUMMY_HASH
        valid_password = verify_password(password, password_hash)
        if not user or not valid_password:
            self.repository.login_failed(user.id if user else None, ip_address)
            raise ValueError("Invalid email or password.")

        issued_at = utc_now().replace(microsecond=0)
        lifetime = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        session = Session(
            id=str(uuid4()),
            token_jti=str(uuid4()),
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent[:512] if user_agent else None,
            created_at=issued_at,
            expires_at=issued_at + lifetime,
        )
        upgraded_hash = (
            hash_password(password) if password_needs_rehash(password_hash) else None
        )
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "jti": session.token_jti,
                "sid": session.id,
            },
            expires_delta=lifetime,
            issued_at=issued_at,
        )
        if not self.repository.start_session(
            user, session, upgraded_hash, expected_hash=password_hash
        ):
            raise ValueError("Invalid email or password.")

        return Token(
            access_token=access_token,
            token_type="bearer",
        )

    def logout(
        self, user_id: int, ip_address: str | None, session_id: str | None = None
    ):
        self.repository.revoke_sessions(user_id, ip_address, session_id)

    def get_profile(self, user_id: int):
        return self.repository.get_profile(user_id)

    def update_profile(self, user_id: int, values: dict, ip_address: str | None):
        return self.repository.update_profile(user_id, values, ip_address)

    def get_preferences(self, user_id: int):
        return self.repository.get_preferences(user_id)

    def update_preferences(self, user_id: int, values: dict, ip_address: str | None):
        return self.repository.update_preferences(user_id, values, ip_address)

    def active_sessions(self, user_id: int):
        return self.repository.active_sessions(user_id)

    def activity(self, user_id: int, limit: int):
        return self.repository.activity(user_id, limit)

    def revoke_session_by_id(
        self, user_id: int, session_id: str, ip_address: str | None
    ) -> bool:
        return self.repository.revoke_session_by_id(user_id, session_id, ip_address)

    def export_user_data(self, user_id: int, ip_address: str | None):
        return self.repository.export_user_data(user_id, ip_address)

    def dashboard(self, user_id: int):
        return self.repository.dashboard(user_id)

    def delete_account(self, user: User, ip_address: str | None):
        self.repository.delete_account(user, ip_address)

    def issue_email_verification(
        self, user_id: int, ip_address: str | None
    ) -> str | None:
        token = generate_verification_token()
        issued = self.repository.issue_verification_token(
            user_id=user_id,
            token_hash=hash_verification_token(token),
            purpose="email_verification",
            expires_at=utc_now() + timedelta(hours=24),
            ip_address=ip_address,
        )
        return token if issued else None

    def request_password_reset(self, email: str, ip_address: str | None) -> str | None:
        user = self.repository.get_by_email(email)
        if user is None:
            return None
        token = generate_verification_token()
        issued = self.repository.issue_verification_token(
            user_id=user.id,
            token_hash=hash_verification_token(token),
            purpose="password_reset",
            expires_at=utc_now() + timedelta(minutes=20),
            ip_address=ip_address,
        )
        return token if issued else None

    def confirm_email_verification(self, token: str, ip_address: str | None) -> None:
        claimed = self.repository.claim_verification_token(
            hash_verification_token(token), "email_verification"
        )
        if claimed is None:
            raise ValueError("Invalid or expired verification token.")
        self.repository.finish_email_verification(claimed, ip_address)

    def confirm_password_reset(
        self, token: str, new_password: str, ip_address: str | None
    ) -> None:
        claimed = self.repository.claim_verification_token(
            hash_verification_token(token), "password_reset"
        )
        if claimed is None:
            raise ValueError("Invalid or expired password reset token.")
        self.repository.replace_password(
            claimed,
            hash_password(new_password),
            "auth.password_reset.completed",
            ip_address,
        )

    def change_password(
        self,
        user: User,
        session: Session,
        current_password: str,
        new_password: str,
        ip_address: str | None,
    ) -> None:
        expected_hash = user.hashed_password
        if not verify_password(current_password, expected_hash):
            raise ValueError("Current password is incorrect.")
        new_hash = hash_password(new_password)
        locked = self.repository.lock_user(user.id)
        if locked is None or locked.hashed_password != expected_hash:
            raise ValueError("Current password is incorrect.")
        if (
            self.repository.get_active_session(user.id, session.token_jti, session.id)
            is None
        ):
            raise ValueError("Session is no longer active.")
        self.repository.replace_password(
            locked,
            new_hash,
            "auth.password_change",
            ip_address,
            keep_session_id=session.id,
        )


def generate_verification_token() -> str:
    return secrets.token_urlsafe(32)


def hash_verification_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
