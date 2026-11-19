from typing import Annotated, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

ID = Annotated[int, Field(gt=0, le=2147483647)]
ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: ShortText = "Research conversation"
    scope_type: Literal["single_paper", "selected_papers", "collection"]
    scope_paper_ids: list[ID] = Field(default_factory=list, max_length=50)
    scope_collection_id: ID | None = None
    language: Literal["en", "bn"] = "en"

    @model_validator(mode="after")
    def validate_scope(self):
        self.scope_paper_ids = list(dict.fromkeys(self.scope_paper_ids))
        if self.scope_type == "collection":
            if self.scope_collection_id is None or self.scope_paper_ids:
                raise ValueError("A collection scope requires only a collection ID.")
        elif (
            self.scope_collection_id is not None
            or not self.scope_paper_ids
            or (self.scope_type == "single_paper" and len(self.scope_paper_ids) != 1)
        ):
            raise ValueError("Select one paper or up to 50 papers for this scope.")
        return self


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=2000)
    ]
    provider: Literal["auto", "offline", "local", "cloud"] = "auto"
    request_id: UUID = Field(default_factory=uuid4)
