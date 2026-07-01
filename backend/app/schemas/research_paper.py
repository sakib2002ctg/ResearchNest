from pydantic import BaseModel, HttpUrl
from typing import Optional


class ResearchPaperCreate(BaseModel):
    title: str
    authors: Optional[str] = None
    abstract: Optional[str] = None
    source: Optional[str] = None
    url: Optional[HttpUrl] = None


class ResearchPaperUpdate(BaseModel):
    title: str
    authors: Optional[str] = None
    abstract: Optional[str] = None
    source: Optional[str] = None
    url: Optional[HttpUrl] = None


class ResearchPaperResponse(BaseModel):
    id: int
    title: str
    authors: Optional[str] = None
    abstract: Optional[str] = None
    source: Optional[str] = None
    url: Optional[HttpUrl] = None

    model_config = {
        "from_attributes": True
    }