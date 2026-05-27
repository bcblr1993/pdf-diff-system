"""应用配置：从环境变量 / .env 加载。"""
from __future__ import annotations
from functools import lru_cache
from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ─────────────────────────────────────
    app_name: str = "PDF Diff"
    app_env: str = "development"
    log_level: str = "INFO"
    secret_key: str = Field(default="dev-secret-change-me", min_length=8)
    access_token_expire_minutes: int = 720

    # ── Postgres ────────────────────────────────
    postgres_user: str = "pdfdiff"
    postgres_password: str = "pdfdiff"
    postgres_db: str = "pdfdiff"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # ── Redis ───────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # ── 存储 ────────────────────────────────────
    storage_dir: str = "./storage"
    cache_dir: str = "./cache"

    # ── Pipeline ────────────────────────────────
    default_dpi: int = 200
    worker_concurrency: int = 2

    # ── 初始管理员（可选） ──────────────────────
    initial_admin_username: str | None = None
    initial_admin_password: str | None = None
    initial_admin_name: str | None = None

    # ── 计算属性 ────────────────────────────────
    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
