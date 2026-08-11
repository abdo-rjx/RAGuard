"""Application configuration loaded from environment / .env via pydantic-settings."""
from functools import lru_cache
from pathlib import Path

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
    JWT_SECRET_KEY: str = "changeme-generate-a-real-secret"
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

    # Policy
    POLICY_YAML_PATH: Path = BASE_DIR / "app" / "policy" / "policies.yaml"

    @property
    def uploads_dir(self) -> Path:
        return BASE_DIR / "data" / "uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
