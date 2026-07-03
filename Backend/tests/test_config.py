from pathlib import Path

import pytest
from pydantic import ValidationError

from github_repo_chat.config import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-123")
    settings = Settings(_env_file=None)
    assert settings.gemini_api_key == "test-key-123"
    assert settings.chroma_persist_dir == Path("./data/chroma")
    assert settings.gemini_embed_model == "gemini-embedding-001"
    assert settings.top_k == 8


def test_settings_requires_gemini_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)
    assert "GEMINI_API_KEY" in str(exc_info.value)


def test_settings_rejects_empty_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "   ")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)
    assert "must not be empty" in str(exc_info.value)


def test_settings_optional_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("TOP_K", "12")
    monkeypatch.setenv("CHROMA_PERSIST_DIR", "./custom/chroma")
    settings = Settings(_env_file=None)
    assert settings.github_token == "ghp_test"
    assert settings.top_k == 12
    assert settings.chroma_persist_dir == Path("./custom/chroma")
