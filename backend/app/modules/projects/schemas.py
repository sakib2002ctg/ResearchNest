from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.ai.schemas import ID

Title = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=300, pattern=r"^[^\x00]*$"
    ),
]
Text = Annotated[str, StringConstraints(max_length=100000, pattern=r"^[^\x00]*$")]
Objective = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=1, max_length=1000, pattern=r"^[^\x00]*$"
    ),
]
ProjectStatus = Literal["planning", "active", "review", "completed", "archived"]
TaskStatus = Literal["todo", "in_progress", "done"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateProject(Input):
    title: Title
    description: Text | None = None
    objectives: list[Objective] = Field(default_factory=list, max_length=100)
    status: ProjectStatus = "planning"
    target_deadline: datetime | None = None
    collection_id: ID | None = None


class UpdateProject(Input):
    title: Title | None = None
    description: Text | None = None
    objectives: list[Objective] | None = Field(None, max_length=100)
    status: ProjectStatus | None = None
    target_deadline: datetime | None = None
    collection_id: ID | None = None
    expected_revision: int | None = Field(None, ge=1)


class AddPaper(Input):
    user_paper_id: ID
    role_in_project: str | None = Field(None, max_length=100, pattern=r"^[^\x00]*$")


class CreateNote(Input):
    title: Title
    content: Text = ""
    user_paper_id: ID | None = None


class UpdateNote(Input):
    title: Title | None = None
    content: Text | None = None
    user_paper_id: ID | None = None


class CreateTask(Input):
    title: Title
    description: Text | None = None
    is_milestone: bool = False
    status: TaskStatus = "todo"
    due_date: datetime | None = None


class UpdateTask(Input):
    title: Title | None = None
    description: Text | None = None
    is_milestone: bool | None = None
    status: TaskStatus | None = None
    due_date: datetime | None = None
