from datetime import datetime
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[int, Field(gt=0, le=2_147_483_647)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
Color = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]
Description = Annotated[str, Field(max_length=2000)]
Content = Annotated[str, Field(min_length=1, max_length=10000)]
AnnotationType = Literal["note", "highlight"]
Status = Literal["unread", "reading", "completed"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def reject_null_characters(self):
        for value in self.model_dump().values():
            if isinstance(value, str) and "\x00" in value:
                raise ValueError("Text cannot contain a null character.")
        return self


class Patch(Input):
    non_nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def require_changes(self):
        fields = self.model_fields_set
        if not fields:
            raise ValueError("At least one field is required.")
        if any(getattr(self, key) is None for key in fields & self.non_nullable):
            raise ValueError("A required value cannot be null.")
        return self


class CollectionCreate(Input):
    name: Name
    description: Description | None = None


class CollectionUpdate(Patch):
    non_nullable = frozenset({"name"})
    name: Name | None = None
    description: Description | None = None


class TagCreate(Input):
    name: Name
    color: Color | None = None


class TagUpdate(Patch):
    non_nullable = frozenset({"name"})
    name: Name | None = None
    color: Color | None = None


class AnnotationCreate(Input):
    type: AnnotationType
    content: Content
    page_number: Identifier | None = None
    color: Color | None = None


class AnnotationUpdate(Patch):
    non_nullable = frozenset({"type", "content"})
    type: AnnotationType | None = None
    content: Content | None = None
    page_number: Identifier | None = None
    color: Color | None = None


class ProgressUpdate(Input):
    reading_status: Status
    reading_progress_percent: float = Field(
        ge=0, le=100, allow_inf_nan=False, strict=True
    )


class Record(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int


class CollectionResult(Record, CollectionCreate):
    created_at: datetime
    updated_at: datetime


class TagResult(Record, TagCreate):
    pass


class AnnotationResult(Record, AnnotationCreate):
    created_at: datetime
    updated_at: datetime


class ProgressResult(Record, ProgressUpdate):
    pass


class DocumentResult(Record):
    user_paper_id: int
    original_filename: str
    size_bytes: int
    page_count: int
    status: Literal["pending", "processing", "completed", "failed"]
    version: int


class LibraryPaperResult(ProgressResult):
    legacy_paper_id: int
    title: str
    authors: str | None
    abstract: str | None
    source: str | None
    url: str | None
    saved_at: datetime
    collection_ids: list[int]
    tag_ids: list[int]
    document: DocumentResult | None


class LibraryPage(BaseModel):
    items: list[LibraryPaperResult]
    page: int
    size: int
    total: int
    pages: int
