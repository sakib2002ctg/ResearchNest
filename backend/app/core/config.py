from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.security_policy import secret_is_strong


class Settings(BaseSettings):
    APP_NAME: str
    DATABASE_URL: str
    DEBUG: bool = False
    APP_ENV: Literal["production", "staging", "local", "development", "test"] = Field(
        "production", validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT")
    )
    HSTS_ENABLED: bool = True
    HSTS_MAX_AGE: int = Field(31536000, ge=0, le=63072000)
    API_RATE_LIMIT_ENABLED: bool = True
    API_RATE_LIMIT_TEST_ENABLED: bool = False
    API_RATE_LIMIT_REQUESTS: int = Field(120, ge=1, le=100000)
    API_RATE_LIMIT_WINDOW_SECONDS: int = Field(60, ge=1, le=86400)
    API_RATE_LIMIT_MAX_CLIENTS: int = Field(10000, ge=1, le=100000)
    READINESS_TIMEOUT_SECONDS: float = Field(2.0, gt=0, le=10)
    READINESS_STORAGE_CACHE_SECONDS: float = Field(1.0, ge=0, le=30)
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
    PGVECTOR_ENABLED: bool = False
    DOCUMENT_WORKER_IN_API: bool = True
    DOCUMENT_EMBEDDING_PROVIDER: Literal["hash", "sentence_transformers"] = "hash"
    DOCUMENT_EMBEDDING_MODEL_PATH: Path | None = None
    AI_DEFAULT_PROVIDER: Literal["offline", "local", "cloud", "auto"] = "offline"
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "llama3.2"
    LOCAL_AI_PROTOCOL: Literal["ollama", "openai"] = "ollama"
    CLOUD_AI_BASE_URL: str = "https://api.openai.com/v1"
    CLOUD_AI_API_KEY: SecretStr | None = None
    CLOUD_AI_MODEL: str = "gpt-4.1-mini"
    AI_HOURLY_REQUEST_LIMIT: int = Field(20, ge=1)
    AI_DAILY_REQUEST_LIMIT: int = Field(100, ge=1)
    AI_HOURLY_TOKEN_LIMIT: int = Field(100000, ge=1)
    AI_DAILY_TOKEN_LIMIT: int = Field(200000, ge=1)
    AI_MAX_CONCURRENT_REQUESTS: int = Field(1, ge=1, le=5)
    AI_MAX_COMPLETION_TOKENS: int = Field(800, ge=64, le=2048)
    AI_MIN_RELEVANCE: float = Field(0.18, ge=0.05, le=1)
    ANALYSIS_MAX_COMPLETION_TOKENS: int = Field(4096, ge=512, le=8192)
    OLLAMA_VISION_MODEL: str = "llama3.2-vision"
    CLOUD_VISION_MODEL: str = "gpt-4.1-mini"
    ASSET_STORAGE_ROOT: Path = Path("storage/assets")
    MULTIMODAL_WORKER_IN_API: bool = True

    @field_validator("OLLAMA_BASE_URL", "CLOUD_AI_BASE_URL")
    @classmethod
    def validate_ai_endpoint(cls, value: str) -> str:
        parts = urlsplit(value)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username
            or parts.password
            or parts.query
            or parts.fragment
        ):
            raise ValueError("AI endpoints must be explicit HTTP(S) server URLs.")
        return value.rstrip("/")

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


def validate_runtime_settings(config: Settings) -> None:
    """Fail before binding a production server; never include secrets in errors."""
    if config.APP_ENV != "production":
        return
    if not secret_is_strong(config.SECRET_KEY):
        raise ValueError("Production SECRET_KEY must be strong and unique.")
    if config.DEBUG:
        raise ValueError("DEBUG must be disabled in production.")
    if not config.CORS_ORIGINS or any(
        not origin.startswith("https://") for origin in config.CORS_ORIGINS
    ):
        raise ValueError("Production CORS_ORIGINS must be explicit HTTPS origins.")
    if not config.JWT_ISSUER.strip() or not config.JWT_AUDIENCE.strip():
        raise ValueError("Production JWT issuer and audience must be configured.")
    if not config.API_RATE_LIMIT_ENABLED:
        raise ValueError("API rate limiting must be enabled in production.")
    if config.ALGORITHM != "HS256":
        raise ValueError("Only the configured HS256 signing policy is supported.")
    if urlsplit(config.DATABASE_URL).scheme.split("+", 1)[0] != "postgresql":
        raise ValueError("Production DATABASE_URL must use PostgreSQL.")


settings = Settings()
