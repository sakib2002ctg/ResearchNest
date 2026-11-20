from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.ai.schemas import ID

Name = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\x00]*$"
    ),
]
Title = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=300, pattern=r"^[^\x00]*$"
    ),
]
Text = Annotated[str, StringConstraints(max_length=100000, pattern=r"^[^\x00]*$")]
Description = Annotated[str, StringConstraints(max_length=10000, pattern=r"^[^\x00]*$")]
EditableRole = Literal["editor", "viewer"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateWorkspace(Input):
    name: Name
    description: Description | None = None


class UpdateWorkspace(Input):
    name: Name | None = None
    description: Description | None = None


class AddMember(Input):
    identifier: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=255, pattern=r"^[^\x00]*$"
        ),
    ]
    role: EditableRole = "viewer"


class UpdateMember(Input):
    role: EditableRole


class ShareCollection(Input):
    collection_id: ID


class CreateNote(Input):
    title: Title
    content: Text = ""
    user_paper_id: ID | None = None


class UpdateNote(Input):
    title: Title | None = None
    content: Text | None = None
    user_paper_id: ID | None = None


PageSize = Annotated[int, Field(ge=1, le=100)]
