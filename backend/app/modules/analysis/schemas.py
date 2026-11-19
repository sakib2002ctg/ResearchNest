from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.modules.ai.gateway import CitationClaim
from app.modules.ai.schemas import ID

FieldName = Literal[
    "abstract_summary",
    "research_problem",
    "research_objectives",
    "methodology",
    "datasets",
    "models_and_algorithms",
    "evaluation_metrics",
    "key_results",
    "contributions",
    "limitations",
    "future_work",
    "strengths",
    "weaknesses",
]
FIELD_NAMES = tuple(FieldName.__args__)
LIST_FIELDS = set(FIELD_NAMES) - {
    "abstract_summary",
    "research_problem",
    "methodology",
    "key_results",
}
MISSING = "Not specified in document"


class Options(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["en", "bn"] = "en"
    force_refresh: bool = False
    provider: Literal["auto", "offline", "local", "cloud"] = "auto"
    request_id: UUID = Field(default_factory=uuid4)


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_paper_ids: list[ID] = Field(min_length=2, max_length=5)
    title: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ] = "Paper comparison"
    language: Literal["en", "bn"] = "en"
    provider: Literal["auto", "offline", "local", "cloud"] = "auto"
    request_id: UUID = Field(default_factory=uuid4)

    @model_validator(mode="after")
    def distinct_papers(self):
        if len(set(self.user_paper_ids)) != len(self.user_paper_ids):
            raise ValueError("Choose 2 to 5 distinct papers.")
        return self


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=1500)
    evidence: list[CitationClaim] = Field(min_length=1, max_length=2)


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: dict[FieldName, list[Claim]] = Field(default_factory=dict, max_length=13)

    @model_validator(mode="after")
    def bounded_claims(self):
        if any(len(claims) > 3 for claims in self.fields.values()):
            raise ValueError("At most three claims per field.")
        return self


class PaperExtraction(Extraction):
    user_paper_id: ID


class SourceClaim(CitationClaim):
    user_paper_id: ID


class SynthesisClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=3000)
    evidence: list[SourceClaim] = Field(min_length=2, max_length=5)


class Gap(SynthesisClaim):
    title: str = Field(min_length=1, max_length=200)


class ComparisonOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    papers: list[PaperExtraction] = Field(min_length=2, max_length=5)
    literature_synthesis: list[SynthesisClaim] = Field(
        default_factory=list, max_length=2
    )
    research_gaps: list[Gap] = Field(default_factory=list, max_length=3)
