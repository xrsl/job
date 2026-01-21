"""Tests for configuration."""

from pathlib import Path


from job.core import Settings


def test_config_from_env(monkeypatch, tmp_path: Path):
    """Test configuration from environment variables."""
    test_db = tmp_path / "test.db"

    # Env var format: JOB_FIELD for top-level, JOB_SECTION__FIELD for nested
    monkeypatch.setenv("JOB_MODEL", "test-model")
    monkeypatch.setenv("JOB_DB_PATH", str(test_db))
    monkeypatch.setenv("JOB_VERBOSE", "true")

    config = Settings()

    assert config.model == "test-model"
    assert config.db_path == str(test_db)
    assert config.verbose is True


def test_config_defaults():
    """Test default configuration values."""
    config = Settings()

    assert config.get_model() == "gemini-2.5-flash"
    assert config.MIN_CONTENT_LENGTH == 500
    assert config.PLAYWRIGHT_TIMEOUT_MS == 30000
    assert config.REQUEST_TIMEOUT == 15


def test_config_mutable():
    """Test that config fields can be updated."""
    config = Settings()

    # Settings are mutable
    config.verbose = True
    assert config.verbose is True

    config.model = "new-model"
    assert config.model == "new-model"
