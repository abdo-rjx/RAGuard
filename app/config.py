"""Application configuration loaded from environment / .env via pydantic-settings."""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Auth
    JWT_SECRET_KEY: str = Field(..., min_length=1)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # Data
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'ragguard.db'}"
    CHROMA_PERSIST_DIR: str = str(BASE_DIR / "data" / "chroma")

    # LLM
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2:1.5b"

    # Embeddings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Environment
    ENVIRONMENT: str = "development"

    # Policy
    POLICY_YAML_PATH: Path = BASE_DIR / "app" / "policy" / "policies.yaml"

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key(cls, v: str) -> str:
        insecure_default = "changeme-generate-a-real-secret"
        if v == insecure_default:
            raise ValueError(
                "JWT_SECRET_KEY must be set to a secure value in environment variables. "
                "The default value is insecure and must be changed. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
            )
        return v

    @property
    def uploads_dir(self) -> Path:
        return BASE_DIR / "data" / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
