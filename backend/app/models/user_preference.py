from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, false
from sqlalchemy.orm import Mapped, mapped_column

from app.database.database import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint("language IN ('en', 'bn')", name="ck_preferences_language"),
        CheckConstraint(
            "theme IN ('system', 'light', 'dark')", name="ck_preferences_theme"
        ),
        CheckConstraint(
            "privacy_default IN ('private', 'public')", name="ck_preferences_privacy"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    language: Mapped[str] = mapped_column(String(2), default="en", server_default="en")
    theme: Mapped[str] = mapped_column(
        String(10), default="system", server_default="system"
    )
    privacy_default: Mapped[str] = mapped_column(
        String(10), default="private", server_default="private"
    )
    allow_external_ai: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
