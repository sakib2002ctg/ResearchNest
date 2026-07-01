from sqlalchemy import Column, Integer, String, Text

from app.database.database import Base


class ResearchPaper(Base):
    __tablename__ = "research_papers"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    authors = Column(String(255))
    abstract = Column(Text)
    source = Column(String(100))
    url = Column(String(500))