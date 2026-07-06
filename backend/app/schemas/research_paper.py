from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class ResearchPaperBase(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Title of the research paper",
    )
    authors: Optional[str] = Field(
        default=None,
        max_length=255,
    )
    abstract: Optional[str] = Field(
        default=None,
        max_length=5000,
    )
    source: Optional[str] = Field(
        default=None,
        max_length=100,
    )
    url: Optional[HttpUrl] = None

    @field_validator("title", "authors", "abstract", "source")
    @classmethod
    def strip_strings(cls, value: Optional[str]):
        if value is None:
            return value
        return value.strip()


class ResearchPaperCreate(ResearchPaperBase):
    pass


class ResearchPaperUpdate(BaseModel):
    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    authors: Optional[str] = Field(
        default=None,
        max_length=255,
    )
    abstract: Optional[str] = Field(
        default=None,
        max_length=5000,
    )
    source: Optional[str] = Field(
        default=None,
        max_length=100,
    )
    url: Optional[HttpUrl] = None

    @field_validator("title", "authors", "abstract", "source")
    @classmethod
    def strip_strings(cls, value: Optional[str]):
        if value is None:
            return value
        return value.strip()


class ResearchPaperResponse(ResearchPaperBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class PaginatedResearchPaperResponse(BaseModel):
    items: list[ResearchPaperResponse]
    page: int
    size: int
    total: int
    pages: int