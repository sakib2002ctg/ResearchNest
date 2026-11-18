from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl

from app.schemas.research_paper import ResearchPaperResponse
from app.schemas.user import UserResponse


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str | None = Field(None, max_length=255)
    bio: str | None = Field(None, max_length=5000)
    institution: str | None = Field(None, max_length=255)
    academic_role: str | None = Field(None, max_length=100)
    avatar_url: HttpUrl | None = Field(None, max_length=2048)


class ProfileResponse(ProfileUpdate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    updated_at: datetime


class PreferenceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["en", "bn"] = "en"
    theme: Literal["system", "light", "dark"] = "system"
    privacy_default: Literal["private", "public"] = "private"
    allow_external_ai: bool = Field(False, strict=True)


class PreferenceResponse(PreferenceUpdate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
    expires_at: datetime


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action: str
    resource_type: str | None
    resource_id: str | None
    details: dict | None
    created_at: datetime


class AuditLogExport(AuditLogResponse):
    user_id: int
    ip_address: str | None


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr


class TokenConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=128)


class PasswordResetConfirmation(TokenConfirmation):
    new_password: str = Field(min_length=8, max_length=128)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class StatusMessage(BaseModel):
    message: str


class EmailVerificationRequested(StatusMessage):
    debug_token: str | None = None


class SavedPaperResponse(ResearchPaperResponse):
    owner_id: int
    created_at: datetime


class DataExport(BaseModel):
    account: UserResponse
    profile: ProfileResponse
    preferences: PreferenceResponse
    papers: list[SavedPaperResponse]
    active_sessions: list[SessionResponse]
    audit_logs: list[AuditLogExport]


class DashboardResponse(BaseModel):
    user: UserResponse
    profile: ProfileResponse
    verification_status: bool
    language: Literal["en", "bn"]
    privacy_default: Literal["private", "public"]
    allow_external_ai: bool
    saved_papers_count: int
    recent_papers: list[SavedPaperResponse]
    active_sessions_count: int
    recent_activity: list[AuditLogResponse]
