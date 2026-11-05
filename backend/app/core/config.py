"""Application settings, loaded from environment variables and backend/.env."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    app_env: str = "dev"  # dev | test | prod
    # Empty -> local SQLite file (backend/data/dev.db). Production: Supabase session pooler URL.
    database_url: str = ""
    sql_echo: bool = False

    jwt_secret: str = "dev-insecure-change-me"
    jwt_expire_minutes: int = 480
    cookie_secure: bool = False
    cookie_name: str = "ats_session"
    recruiter_invite_code: str = ""
    max_upload_mb: int = 5
    register_rate_limit_per_hour: int = 20  # sign-ups per IP per hour

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    llm_timeout_seconds: float = 90.0
    deepseek_fallback_model: str = ""  # optional stronger model tried once when the primary cannot produce valid JSON
    chat_enabled: bool = True  # in-app assistant (falls back to a small FAQ without an API key)
    chat_model: str = ""  # empty -> deepseek_model
    chat_max_tokens: int = 700
    default_phone_region: str = "PK"  # ISO region assumed for phone numbers without a country code

    # Outgoing email (SMTP). When unset, verification codes fall back to the simulated outbox.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_security: str = "starttls"  # starttls | ssl | none
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "RC3 Talent Intelligence"
    smtp_timeout_seconds: float = 15.0

    aws_bearer_token_bedrock: str = ""
    aws_region: str = "us-east-1"
    bedrock_embed_model: str = "amazon.titan-embed-text-v2:0"
    embedding_dim: int = 1024

    sem_strong: float = 0.55
    sem_weak: float = 0.40

    tasks_eager: bool = False  # run background tasks inline (tests)
    task_workers: int = 4

    @property
    def resolved_database_url(self) -> str:
        url = (self.database_url or "").strip()
        if not url:
            data_dir = BACKEND_DIR / "data"
            data_dir.mkdir(exist_ok=True)
            return f"sqlite:///{(data_dir / 'dev.db').as_posix()}"
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = "postgresql+psycopg://" + url[len("postgresql://") :]
        return url

    @property
    def smtp_enabled(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.smtp_password and self.smtp_from_email)

    @property
    def is_sqlite(self) -> bool:
        return self.resolved_database_url.startswith("sqlite")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
