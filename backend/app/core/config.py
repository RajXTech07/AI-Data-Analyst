from pathlib import Path
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # App
    APP_ENV: Literal["development", "production", "test"] = "development"
    API_PORT: int = 8000
    WEB_ORIGIN: str = "http://localhost:3000"
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "sqlite:///./analyst.db"

    # Storage
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    STORAGE_DIR: str = "./storage"
    MAX_UPLOAD_MB: int = 10

    # Auth
    JWT_SECRET: str = "change-me-to-a-long-random-string-at-least-32-chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 15
    REFRESH_TOKEN_DAYS: int = 7

    # LLM
    LLM_PROVIDER: Literal["gemini", "openai"] = "gemini"
    GEMINI_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    LLM_MODEL: str = "gemini-3.5-flash-lite"
    LLM_MAX_TOOL_CALLS: int = 12
    LLM_TIMEOUT_SECONDS: int = 60

    # Limits & Execution
    TOOL_TIMEOUT_SECONDS: int = 60
    MAX_ROWS: int = 200000
    MAX_ROWS_EXACT: int = 50_000_000
    MEMORY_BUDGET_MB: int = 2048
    MAX_PLOT_POINTS: int = 50_000
    MAX_GROUPS_DEFAULT: int = 20
    CHUNK_SIZE_INGESTION: int = 100_000

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_MB * 1024 * 1024

    @property
    def resolved_storage_path(self) -> Path:
        p = Path(self.STORAGE_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

settings = Settings()
