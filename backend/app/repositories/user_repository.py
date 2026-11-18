from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.audit_log import AuditLog
from app.models.profile import Profile
from app.models.session import Session as UserSession
from app.models.user import User
from app.models.user_preference import UserPreference
from app.repositories.audit_repository import add_audit


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, user: User, ip_address: str | None = None) -> User:
        self.db.add(user)
        self.db.flush()
        add_audit(
            self.db, "user.register", user.id, ip_address, resource_id=str(user.id)
        )
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_by_id(self, user_id: int) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_username(self, username: str) -> User | None:
        return self.db.query(User).filter(User.username == username).first()

    def login_failed(self, user_id: int | None, ip_address: str | None) -> None:
        add_audit(self.db, "auth.login.failed", user_id, ip_address)
        self.db.commit()

    def start_session(
        self, user: User, session: UserSession, upgraded_hash: str | None = None
    ) -> None:
        if upgraded_hash is not None:
            user.hashed_password = upgraded_hash
        self.db.add(session)
        add_audit(self.db, "auth.login.success", user.id, session.ip_address)
        self.db.commit()

    def get_active_session(
        self, user_id: int, jti: str, sid: str
    ) -> UserSession | None:
        return (
            self.db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.token_jti == jti,
                UserSession.id == sid,
                UserSession.is_revoked.is_(False),
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > utc_now(),
            )
            .first()
        )

    def revoke_sessions(
        self, user_id: int, ip_address: str | None, session_id: str | None = None
    ) -> None:
        query = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_revoked.is_(False),
            UserSession.expires_at > utc_now(),
        )
        if session_id is not None:
            query = query.filter(UserSession.id == session_id)
        query.update(
            {"is_revoked": True, "revoked_at": utc_now()}, synchronize_session=False
        )
        action = "auth.logout" if session_id is not None else "auth.logout_all"
        add_audit(self.db, action, user_id, ip_address)
        self.db.commit()

    def get_profile(self, user_id: int) -> Profile:
        profile = self.db.query(Profile).filter(Profile.user_id == user_id).first()
        if profile is None:
            profile = Profile(user_id=user_id)
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    def update_profile(
        self, user_id: int, values: dict, ip_address: str | None
    ) -> Profile:
        profile = self.get_profile(user_id)
        for key, value in values.items():
            setattr(profile, key, value)
        add_audit(
            self.db,
            "user.profile.update",
            user_id,
            ip_address,
            details={"fields": sorted(values)},
        )
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def get_preferences(self, user_id: int) -> UserPreference:
        preferences = (
            self.db.query(UserPreference)
            .filter(UserPreference.user_id == user_id)
            .first()
        )
        if preferences is None:
            preferences = UserPreference(user_id=user_id)
            self.db.add(preferences)
            self.db.commit()
            self.db.refresh(preferences)
        return preferences

    def update_preferences(
        self, user_id: int, values: dict, ip_address: str | None
    ) -> UserPreference:
        preferences = self.get_preferences(user_id)
        for key, value in values.items():
            setattr(preferences, key, value)
        add_audit(
            self.db,
            "user.preferences.update",
            user_id,
            ip_address,
            details={"fields": sorted(values)},
        )
        self.db.commit()
        self.db.refresh(preferences)
        return preferences

    def active_sessions(self, user_id: int) -> list[UserSession]:
        return (
            self.db.query(UserSession)
            .filter(
                UserSession.user_id == user_id,
                UserSession.is_revoked.is_(False),
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > utc_now(),
            )
            .order_by(UserSession.created_at.desc(), UserSession.id)
            .all()
        )

    def activity(self, user_id: int, limit: int) -> list[AuditLog]:
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(limit)
            .all()
        )

    def delete_account(self, user: User, ip_address: str | None) -> None:
        add_audit(
            self.db,
            "user.account.delete",
            user.id,
            ip_address,
            resource_id=str(user.id),
        )
        self.db.flush()
        self.db.delete(user)
        self.db.commit()
