from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    github_token: str | None = Field(default=None, alias="GITHUB_TOKEN")
    chroma_persist_dir: Path = Field(
        default=Path("./data/chroma"),
        alias="CHROMA_PERSIST_DIR",
    )
    gemini_embed_model: str = Field(
        default="gemini-embedding-001",
        alias="GEMINI_EMBED_MODEL",
    )
    gemini_chat_model: str = Field(
        default="gemini-2.0-flash",
        alias="GEMINI_CHAT_MODEL",
    )
    max_chunk_tokens: int = Field(default=512, alias="MAX_CHUNK_TOKENS")
    chunk_overlap_tokens: int = Field(default=50, alias="CHUNK_OVERLAP_TOKENS")
    top_k: int = Field(default=8, alias="TOP_K")

    @field_validator("gemini_api_key")
    @classmethod
    def api_key_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("GEMINI_API_KEY must not be empty")
        return value.strip()


def get_settings() -> Settings:
    return Settings()
