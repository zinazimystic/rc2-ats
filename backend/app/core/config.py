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

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    llm_timeout_seconds: float = 90.0

    aws_bearer_token_bedrock: str = ""
    aws_region: str = "us-east-1"
    bedrock_embed_model: str = "amazon.titan-embed-text-v2:0"
    embedding_dim: int = 1024

    sem_strong: float = 0.55
    sem_weak: float = 0.40

    tasks_eager: bool = False  # run background tasks inline (tests)
    task_workers: int = 3

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
    def is_sqlite(self) -> bool:
        return self.resolved_database_url.startswith("sqlite")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
