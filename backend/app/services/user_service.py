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
            hash_password(password)
            if password_needs_rehash(user.hashed_password)
            else None
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
        self.repository.start_session(user, session, upgraded_hash)

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

    def delete_account(self, user: User, ip_address: str | None):
        self.repository.delete_account(user, ip_address)
