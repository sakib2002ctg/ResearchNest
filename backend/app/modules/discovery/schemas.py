from datetime import date
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

DiscoverySource = Literal["arxiv", "openalex", "crossref", "semantic_scholar", "pubmed"]
DiscoverySort = Literal["relevance", "date"]
SearchField = Literal["all", "title", "author", "id"]
PublicationType = Literal[
    "article", "review", "preprint", "book", "book_chapter", "conference", "other"
]


class DiscoverySearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(min_length=2, max_length=300)
    sources: list[DiscoverySource] = Field(
        default_factory=lambda: [
            "arxiv",
            "openalex",
            "crossref",
            "semantic_scholar",
            "pubmed",
        ],
        min_length=1,
        max_length=5,
    )
    year_from: int | None = Field(None, ge=1800, le=2200)
    year_to: int | None = Field(None, ge=1800, le=2200)
    publication_type: PublicationType | None = None
    sort: DiscoverySort = "relevance"
    field: SearchField = "all"
    limit: int = Field(20, ge=1, le=50)
    offset: int = Field(0, ge=0, le=250)

    @field_validator("q")
    @classmethod
    def clean_query(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Search query must contain at least two characters.")
        return value

    @field_validator("sources")
    @classmethod
    def unique_sources(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_year_range(self):
        if self.year_from is not None and self.year_to is not None:
            if self.year_from > self.year_to:
                raise ValueError("year_from must not be later than year_to.")
        return self


class CitationLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=500)
    doi: str | None = None
    url: HttpUrl | None = None
    source: DiscoverySource


class DiscoveryPaper(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=500)
    authors: list[str] = Field(default_factory=list, max_length=100)
    abstract: str | None = Field(None, max_length=20000)
    doi: str | None = Field(None, max_length=255)
    publication_date: date | None = None
    url: HttpUrl | None = None
    source: DiscoverySource
    sources: list[DiscoverySource] = Field(default_factory=list, max_length=5)
    external_id: str | None = Field(None, max_length=255)
    paper_type: str | None = Field(None, max_length=64)
    citation_count: int | None = Field(None, ge=0)
    citation_links: list[CitationLink] = Field(default_factory=list, max_length=20)


class DiscoverySearchResponse(BaseModel):
    items: list[DiscoveryPaper]
    total: int
    offset: int
    limit: int
    sources: list[DiscoverySource]
    warnings: list[str] = Field(default_factory=list)


class SaveToLibraryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source: DiscoverySource
    external_id: str | None = Field(None, min_length=1, max_length=255)
    doi: str | None = Field(None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def requires_identifier(self):
        if not (self.external_id or self.doi):
            raise ValueError("A provider ID or DOI is required.")
        return self


class SaveToLibraryResponse(BaseModel):
    paper_id: int
    user_paper_id: int
    saved: bool
    already_saved: bool
