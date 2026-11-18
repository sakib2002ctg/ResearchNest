from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


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
