from functools import lru_cache
from pathlib import Path
from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Production deployments commonly keep .env at repository root, while
        # local backend-only deployments keep it beside this application.
        env_file=(BACKEND_DIR.parent / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Food Safety Operating System"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    cors_origins: list[str] = []
    database_url: SecretStr = SecretStr("")
    admin_database_url: SecretStr = SecretStr("")
    readiness_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    redis_url: SecretStr = SecretStr("redis://localhost:6379/0")
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: SecretStr = SecretStr("")
    mqtt_consumer_enabled: bool = False
    mqtt_tenant_id: UUID | None = None
    jwt_secret: SecretStr = SecretStr("")
    jwt_access_token_minutes: int = 15
    jwt_refresh_token_days: int = 7
    google_map_api_key: SecretStr = SecretStr("")
    routing_timeout_seconds: float = Field(default=5.0, gt=0, le=30)
    openai_api_key: SecretStr = SecretStr("")
    upload_dir: Path = BACKEND_DIR.parent / "var" / "uploads"
    upload_max_bytes: int = Field(default=10 * 1024 * 1024, gt=0, le=50 * 1024 * 1024)


@lru_cache
def get_settings() -> Settings:
    return Settings()
