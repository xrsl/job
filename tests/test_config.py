"""Tests for configuration."""

from pathlib import Path

import pytest

from job.core import Config


def test_config_from_env(monkeypatch, tmp_path: Path):
    """Test configuration from environment variables."""
    test_db = tmp_path / "test.db"

    monkeypatch.setenv("JOB_MODEL", "test-model")
    monkeypatch.setenv("JOB_DB_PATH", str(test_db))

    config = Config.from_env(verbose=True)

    assert config.model == "test-model"
    assert config.db_path == test_db
    assert config.verbose is True


def test_config_defaults():
    """Test default configuration values."""
    config = Config.from_env()

    assert config.model == "gemini-2.5-flash"
    assert config.MIN_CONTENT_LENGTH == 500
    assert config.PLAYWRIGHT_TIMEOUT_MS == 30000
    assert config.REQUEST_TIMEOUT == 15


def test_config_frozen():
    """Test that config is immutable."""
    config = Config.from_env()

    with pytest.raises(Exception):  # FrozenInstanceError
        config.model = "new-model"  # type: ignore
