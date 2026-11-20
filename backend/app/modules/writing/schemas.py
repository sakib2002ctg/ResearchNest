from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.ai.gateway import CitationClaim
from app.modules.ai.schemas import ID

DocType = Literal["research_paper", "research_proposal", "thesis", "literature_review"]
Title = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=300, pattern=r"^[^\x00]*$"
    ),
]
Heading = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\x00]*$"
    ),
]
Content = Annotated[str, StringConstraints(max_length=200000, pattern=r"^[^\x00]*$")]


class CreateDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    doc_type: DocType
    title: Title
    language: Literal["en", "bn"] = "en"
    outline: list[Heading] | None = Field(None, max_length=60)
    content_markdown: Content = ""
    cited_citation_ids: list[ID] = Field(default_factory=list, max_length=200)


class UpdateDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Title | None = None
    language: Literal["en", "bn"] | None = None
    doc_type: DocType | None = None
    outline: list[Heading] | None = Field(None, max_length=60)
    content_markdown: Content | None = None
    cited_citation_ids: list[ID] | None = Field(None, max_length=200)
    create_version: bool = False
    change_summary: str | None = Field(None, max_length=300, pattern=r"^[^\x00]*$")
    expected_revision: int | None = Field(None, ge=1)


class RestoreVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int | None = Field(None, ge=1)


class AssistRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["draft_section", "tone", "grammar", "paraphrase"]
    section: Literal[
        "abstract",
        "introduction",
        "literature_review",
        "methodology",
        "results_discussion",
    ] = "introduction"
    text: str | None = Field(
        None, min_length=1, max_length=10000, pattern=r"^[^\x00]*$"
    )
    user_paper_ids: list[ID] = Field(default_factory=list, max_length=5)
    provider: Literal["auto", "offline", "local", "cloud"] = "auto"
    request_id: UUID = Field(default_factory=uuid4)


class DraftParagraph(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1500, pattern=r"^[^\x00]*$")
    evidence: list[CitationClaim] = Field(default_factory=list, max_length=2)


class DraftOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paragraphs: list[DraftParagraph] = Field(default_factory=list, max_length=8)
