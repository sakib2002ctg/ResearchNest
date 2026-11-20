from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.ai.gateway import CitationClaim


class ProgressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    completed_step_ids: list[
        Annotated[str, StringConstraints(min_length=1, max_length=100)]
    ] = Field(max_length=100)


class ExplainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["en", "bn"] = "en"
    provider: Literal["auto", "offline", "local", "cloud"] = "auto"
    request_id: UUID = Field(default_factory=uuid4)


class PlainLanguageSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    focus: Literal["question", "method", "findings", "limitations"]
    explanation: str = Field(min_length=10, max_length=1000)
    citations: list[CitationClaim] = Field(min_length=1, max_length=2)


class ExplanationSelection(BaseModel):
    """Source quotes remain distinct from tentative plain-language interpretation."""

    model_config = ConfigDict(extra="forbid")
    citations: list[CitationClaim] = Field(default_factory=list, max_length=5)
    sections: list[PlainLanguageSection] = Field(default_factory=list, max_length=3)
