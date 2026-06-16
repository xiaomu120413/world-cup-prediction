from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "World Cup Prediction API"
    app_version: str = "0.1.0"
    api_version: str = "v1"
    environment: str = "local"
    admin_token: str = "change-me"
    allowed_origins: str = "http://127.0.0.1:4173,http://localhost:4173"
    data_backend: str = "database"
    database_url: str = "postgresql+psycopg://worldcup:worldcup@127.0.0.1:54321/worldcup_prediction"
    cache_enabled: bool = False
    cache_ttl_seconds: int = 60
    redis_url: str = "redis://127.0.0.1:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def allowed_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
