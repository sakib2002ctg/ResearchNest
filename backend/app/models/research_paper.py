from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database.database import Base


class ResearchPaper(Base):
    __tablename__ = "research_papers"
    __table_args__ = (
        Index("ix_research_papers_owner_created_id", "owner_id", "created_at", "id"),
        UniqueConstraint("owner_id", "id", name="uq_research_papers_owner_id_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    authors = Column(String(255))
    abstract = Column(Text)
    source = Column(String(100))
    url = Column(String(500))
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    owner_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    owner = relationship(
        "User",
        back_populates="papers",
    )
