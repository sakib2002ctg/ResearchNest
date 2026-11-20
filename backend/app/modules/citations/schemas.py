from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.modules.ai.schemas import ID
from app.modules.discovery.gateway import normalize_doi

Style = Literal["apa", "ieee", "mla", "chicago", "harvard"]
EntryType = Literal["article", "inproceedings", "book", "misc", "preprint"]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
AuthorName = Annotated[Text, Field(max_length=250)]
CiteKey = Annotated[str, StringConstraints(pattern=r"^[A-Za-z][A-Za-z0-9:_-]{0,99}$")]


class CitationInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    user_paper_id: ID | None = None
    cite_key: CiteKey | None = None
    entry_type: EntryType = "article"
    title: Annotated[Text, Field(max_length=500)] | None = None
    authors: list[AuthorName] = Field(default_factory=list, max_length=100)
    year: int | None = Field(None, ge=1000, le=2200)
    venue: str | None = Field(None, max_length=500)
    volume: str | None = Field(None, max_length=50)
    issue: str | None = Field(None, max_length=50)
    pages: str | None = Field(None, max_length=100)
    doi: str | None = Field(None, max_length=255)
    url: str | None = Field(None, max_length=2048)
    publisher: str | None = Field(None, max_length=500)

    @field_validator("doi")
    @classmethod
    def valid_doi(cls, value):
        if value is None:
            return None
        normalized = normalize_doi(value)
        if normalized is None:
            raise ValueError("Invalid DOI.")
        return normalized

    @field_validator("url")
    @classmethod
    def public_url(cls, value):
        if value is None:
            return None
        from urllib.parse import urlsplit

        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
        ):
            raise ValueError("Citation URLs must be HTTP(S) without credentials.")
        return value

    @field_validator("title", "venue", "volume", "issue", "pages", "publisher", "url")
    @classmethod
    def safe_text(cls, value):
        if value is not None and any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Citation metadata must not contain control characters.")
        return value

    @field_validator("authors")
    @classmethod
    def safe_authors(cls, value):
        if any(any(ord(c) < 32 or ord(c) == 127 for c in author) for author in value):
            raise ValueError("Author names must not contain control characters.")
        return value

    @model_validator(mode="after")
    def has_source(self):
        if not (self.title or self.user_paper_id or self.doi):
            raise ValueError("Provide a title, owned library paper, or DOI.")
        return self


class CitationUpdate(CitationInput):
    entry_type: EntryType | None = None

    @model_validator(mode="after")
    def has_source(self):
        for required in ("title", "authors", "entry_type", "cite_key"):
            if required in self.model_fields_set and getattr(self, required) is None:
                raise ValueError(f"{required} cannot be null.")
        return self


class CitationResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_paper_id: int | None
    cite_key: str
    entry_type: EntryType
    title: str
    authors: list[str]
    year: int | None
    venue: str | None
    volume: str | None
    issue: str | None
    pages: str | None
    doi: str | None
    url: str | None
    publisher: str | None
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    warnings: list[str] = Field(default_factory=list)


class ImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["bibtex", "ris"]
    content: str = Field(min_length=1, max_length=500000)


class FormatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    citation_ids: list[ID] = Field(min_length=1, max_length=200)
    style: Style = "apa"

    @field_validator("citation_ids")
    @classmethod
    def distinct_ids(cls, value):
        return list(dict.fromkeys(value))
