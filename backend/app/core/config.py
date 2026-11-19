from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str
    DATABASE_URL: str
    DEBUG: bool = False
    APP_ENV: Literal["production", "staging", "local", "development", "test"] = (
        "production"
    )
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
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
    REDIS_URL: str | None = Field(None, repr=False)
    OPENALEX_API_KEY: SecretStr | None = None
    SEMANTIC_SCHOLAR_API_KEY: SecretStr | None = None
    PUBMED_TOOL_EMAIL: str | None = None
    PUBMED_API_KEY: SecretStr | None = None
    PDF_STORAGE_ROOT: Path = Path("storage/pdfs")
    CLAMAV_HOST: str | None = None
    CLAMAV_PORT: int = Field(3310, ge=1, le=65535)
    CLAMAV_TIMEOUT_SECONDS: float = Field(10.0, gt=0, le=60)

    @field_validator("CORS_ORIGINS")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            parts = urlsplit(origin)
            if (
                parts.scheme not in {"http", "https"}
                or not parts.netloc
                or parts.username is not None
                or parts.password is not None
                or parts.path
                or parts.query
                or parts.fragment
                or "*" in origin
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins.")
            try:
                _ = parts.port
            except ValueError as exc:
                raise ValueError("CORS origin has an invalid port.") from exc
        return list(dict.fromkeys(origins))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
