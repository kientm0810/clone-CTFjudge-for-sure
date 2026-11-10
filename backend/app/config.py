from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str = "change-me"
    database_url: str = "postgresql+asyncpg://ctfjudge:ctfjudge@postgres:5432/ctfjudge"
    redis_url: str = "redis://redis:6379/0"
    default_chat_model: str = "ollama/qwen2.5:3b"
    default_embedding_model: str = "ollama/nomic-embed-text"
    default_temperature: float = 0.1
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_timeout_seconds: float = 180
    upload_dir: str = "/data/uploads"
    artifact_dir: str = "/data/artifacts"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

