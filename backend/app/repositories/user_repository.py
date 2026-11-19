from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.models.audit_log import AuditLog
from app.models.library import (
    Annotation,
    Collection,
    CollectionPaper,
    Document,
    PaperTag,
    Tag,
)
from app.models.paper import UserPaper
from app.models.profile import Profile
from app.models.research_paper import ResearchPaper
from app.models.session import Session as UserSession
from app.models.user import User
from app.models.user_preference import UserPreference
from app.models.verification_token import VerificationToken
from app.modules.library.cleanup import queue_owned_pdfs
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
        self,
        user: User,
        session: UserSession,
        upgraded_hash: str | None = None,
        *,
        expected_hash: str,
    ) -> bool:
        locked = self.lock_user(user.id)
        if locked is None or locked.hashed_password != expected_hash:
            return False
        if upgraded_hash is not None:
            locked.hashed_password = upgraded_hash
        self.db.add(session)
        add_audit(self.db, "auth.login.success", user.id, session.ip_address)
        self.db.commit()
        return True

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
        if self.lock_user(user_id) is None:
            return
        now = utc_now()
        query = self.db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.is_revoked.is_(False),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        if session_id is not None:
            query = query.filter(UserSession.id == session_id)
        query.update({"is_revoked": True, "revoked_at": now}, synchronize_session=False)
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
        if (user := self.lock_user(user.id)) is None:
            return
        add_audit(
            self.db,
            "user.account.delete",
            user.id,
            ip_address,
            resource_id=str(user.id),
        )
        self.db.flush()
        queue_owned_pdfs(self.db, user.id)
        self.db.delete(user)
        self.db.commit()

    def lock_user(self, user_id: int) -> User | None:
        # Serialize credential mutations, session creation and token work per account.
        return (
            self.db.query(User)
            .filter(User.id == user_id)
            .populate_existing()
            .with_for_update()
            .first()
        )

    def invalidate_tokens(self, user_id: int, purpose: str, now: datetime) -> None:
        self.db.query(VerificationToken).filter(
            VerificationToken.user_id == user_id,
            VerificationToken.purpose == purpose,
            VerificationToken.used_at.is_(None),
        ).update({"used_at": now}, synchronize_session=False)

    def issue_verification_token(
        self,
        user_id: int,
        token_hash: str,
        purpose: str,
        expires_at: datetime,
        ip_address: str | None,
    ) -> bool:
        user = self.lock_user(user_id)
        if user is None or (purpose == "email_verification" and user.is_verified):
            return False
        now = utc_now()
        requests = (
            self.db.query(func.count(VerificationToken.id))
            .filter(
                VerificationToken.user_id == user_id,
                VerificationToken.purpose == purpose,
                VerificationToken.created_at
                > now - timedelta(seconds=settings.IDENTITY_REQUEST_WINDOW_SECONDS),
            )
            .scalar()
        )
        if requests >= settings.IDENTITY_REQUEST_LIMIT:
            return False
        self.invalidate_tokens(user_id, purpose, now)
        self.db.add(
            VerificationToken(
                user_id=user_id,
                token_hash=token_hash,
                purpose=purpose,
                expires_at=expires_at,
            )
        )
        action = (
            "auth.email_verification.requested"
            if purpose == "email_verification"
            else "auth.password_reset.requested"
        )
        add_audit(self.db, action, user_id, ip_address)
        self.db.commit()
        return True

    def claim_verification_token(self, token_hash: str, purpose: str) -> User | None:
        query = self.db.query(VerificationToken).filter(
            VerificationToken.token_hash == token_hash,
            VerificationToken.purpose == purpose,
            VerificationToken.used_at.is_(None),
        )
        user_id = (
            query.filter(VerificationToken.expires_at > utc_now())
            .with_entities(VerificationToken.user_id)
            .scalar()
        )
        # Lock in the same order as issuance, then recheck after waiting.
        if user_id is None or (user := self.lock_user(user_id)) is None:
            return None
        now = utc_now()
        claimed = query.filter(
            VerificationToken.user_id == user_id,
            VerificationToken.expires_at > now,
        ).update({"used_at": now}, synchronize_session=False)
        return user if claimed == 1 else None

    def finish_email_verification(self, user: User, ip_address: str | None) -> None:
        user.is_verified = True
        add_audit(self.db, "auth.email_verification.confirmed", user.id, ip_address)
        self.db.commit()

    def replace_password(
        self,
        user: User,
        new_password_hash: str,
        action: str,
        ip_address: str | None,
        keep_session_id: str | None = None,
    ) -> None:
        now = utc_now()
        user.hashed_password = new_password_hash
        self.invalidate_tokens(user.id, "password_reset", now)
        sessions = self.db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.is_revoked.is_(False),
            UserSession.revoked_at.is_(None),
            UserSession.expires_at > now,
        )
        if keep_session_id is not None:
            sessions = sessions.filter(UserSession.id != keep_session_id)
        sessions.update(
            {"is_revoked": True, "revoked_at": now}, synchronize_session=False
        )
        add_audit(self.db, action, user.id, ip_address)
        self.db.commit()

    def revoke_session_by_id(
        self, user_id: int, session_id: str, ip_address: str | None
    ) -> bool:
        if self.lock_user(user_id) is None:
            return False
        now = utc_now()
        session = (
            self.db.query(UserSession)
            .filter(
                UserSession.id == session_id,
                UserSession.user_id == user_id,
                UserSession.is_revoked.is_(False),
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
            .with_for_update()
            .first()
        )
        if session is None:
            return False
        session.is_revoked = True
        session.revoked_at = now
        add_audit(
            self.db,
            "auth.session.revoked",
            user_id,
            ip_address,
            resource_type="session",
            resource_id=session_id,
        )
        self.db.commit()
        return True

    def export_user_data(self, user_id: int, ip_address: str | None) -> dict:
        add_audit(self.db, "user.data.exported", user_id, ip_address)
        self.db.commit()
        user = self.get_by_id(user_id)
        profile = self.get_profile(user_id)
        preferences = self.get_preferences(user_id)
        papers = (
            self.db.query(ResearchPaper)
            .filter(ResearchPaper.owner_id == user_id)
            .order_by(ResearchPaper.created_at.desc(), ResearchPaper.id.desc())
            .all()
        )
        sessions = self.active_sessions(user_id)
        audit_logs = (
            self.db.query(AuditLog)
            .filter(AuditLog.user_id == user_id)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .all()
        )
        library_items = (
            self.db.query(UserPaper)
            .filter(UserPaper.user_id == user_id)
            .order_by(UserPaper.saved_at, UserPaper.id)
            .all()
        )
        library_ids = [item.id for item in library_items]
        collection_ids: dict[int, list[int]] = {}
        tag_ids: dict[int, list[int]] = {}
        annotations: dict[int, list[Annotation]] = {}
        documents: dict[int, Document] = {}
        if library_ids:
            for paper_id, collection_id in (
                self.db.query(
                    CollectionPaper.user_paper_id, CollectionPaper.collection_id
                )
                .filter(
                    CollectionPaper.user_id == user_id,
                    CollectionPaper.user_paper_id.in_(library_ids),
                )
                .all()
            ):
                collection_ids.setdefault(paper_id, []).append(collection_id)
            for paper_id, tag_id in (
                self.db.query(PaperTag.user_paper_id, PaperTag.tag_id)
                .filter(
                    PaperTag.user_id == user_id, PaperTag.user_paper_id.in_(library_ids)
                )
                .all()
            ):
                tag_ids.setdefault(paper_id, []).append(tag_id)
            for annotation in (
                self.db.query(Annotation)
                .filter(
                    Annotation.user_id == user_id,
                    Annotation.user_paper_id.in_(library_ids),
                )
                .order_by(Annotation.created_at, Annotation.id)
                .all()
            ):
                annotations.setdefault(annotation.user_paper_id, []).append(annotation)
            documents = {
                document.user_paper_id: document
                for document in self.db.query(Document)
                .filter(
                    Document.user_id == user_id,
                    Document.user_paper_id.in_(library_ids),
                )
                .all()
            }
        collections = (
            self.db.query(Collection)
            .filter(Collection.user_id == user_id)
            .order_by(Collection.id)
            .all()
        )
        tags = self.db.query(Tag).filter(Tag.user_id == user_id).order_by(Tag.id).all()
        library_export = [
            {
                "user_paper_id": item.id,
                "legacy_paper_id": item.legacy_paper_id,
                "reading_status": item.reading_status,
                "reading_progress_percent": item.reading_progress_percent,
                "collection_ids": collection_ids.get(item.id, []),
                "tag_ids": tag_ids.get(item.id, []),
                "annotations": annotations.get(item.id, []),
                "document": (
                    {
                        "id": documents[item.id].id,
                        "user_paper_id": item.id,
                        "original_filename": documents[item.id].original_filename,
                        "size_bytes": documents[item.id].size_bytes,
                        "page_count": documents[item.id].page_count,
                        "created_at": documents[item.id].created_at,
                    }
                    if item.id in documents
                    else None
                ),
            }
            for item in library_items
        ]
        return {
            "account": user,
            "profile": profile,
            "preferences": preferences,
            "papers": papers,
            "collections": collections,
            "tags": tags,
            "library_items": library_export,
            "active_sessions": sessions,
            "audit_logs": audit_logs,
        }

    def dashboard(self, user_id: int) -> dict:
        user = self.get_by_id(user_id)
        profile = self.get_profile(user_id)
        preferences = self.get_preferences(user_id)
        papers_count = (
            self.db.query(func.count(ResearchPaper.id))
            .filter(ResearchPaper.owner_id == user_id)
            .scalar()
        )
        recent_papers = (
            self.db.query(ResearchPaper)
            .filter(ResearchPaper.owner_id == user_id)
            .order_by(ResearchPaper.created_at.desc(), ResearchPaper.id.desc())
            .limit(5)
            .all()
        )
        sessions_count = (
            self.db.query(func.count(UserSession.id))
            .filter(
                UserSession.user_id == user_id,
                UserSession.is_revoked.is_(False),
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > utc_now(),
            )
            .scalar()
        )
        recent_activity = self.activity(user_id, limit=5)
        return {
            "user": user,
            "profile": profile,
            "verification_status": user.is_verified,
            "language": preferences.language,
            "privacy_default": preferences.privacy_default,
            "allow_external_ai": preferences.allow_external_ai,
            "saved_papers_count": papers_count,
            "recent_papers": recent_papers,
            "active_sessions_count": sessions_count,
            "recent_activity": recent_activity,
        }
