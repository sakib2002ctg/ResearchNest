from sqlalchemy import String, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        index=True,
    )

    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(
        default=False,
        server_default=false(),
        nullable=False,
    )

    papers = relationship(
        "ResearchPaper",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    profile = relationship("Profile", uselist=False, cascade="all, delete-orphan")
    preferences = relationship(
        "UserPreference", uselist=False, cascade="all, delete-orphan"
    )
    sessions = relationship(
        "Session", cascade="all, delete-orphan", passive_deletes=True
    )
    verification_tokens = relationship(
        "VerificationToken", cascade="all, delete-orphan", passive_deletes=True
    )
