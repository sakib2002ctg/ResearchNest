from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    DATABASE_URL: str
    DEBUG: bool = False
    APP_ENV: Literal["production", "staging", "local", "development", "test"] = (
        "production"
    )
    IDENTITY_REQUEST_LIMIT: int = Field(5, ge=1, le=100)
    IDENTITY_REQUEST_WINDOW_SECONDS: int = Field(600, ge=1, le=86400)

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(30, gt=0)
    JWT_ISSUER: str = "researchnest-api"
    JWT_AUDIENCE: str = "researchnest-client"

    SMTP_HOST: str | None = None
    SMTP_PORT: int | None = Field(None, ge=1, le=65535)
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: SecretStr | None = None
    SMTP_FROM: str | None = None
    SMTP_USE_SSL: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
