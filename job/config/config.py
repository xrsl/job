"""Configuration settings with TOML and environment variable support."""

import os
from pathlib import Path
from typing import ClassVar

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .extensions import JobAdd, JobExport, JobFit, JobGH, JobSearch


class Settings(BaseSettings):
    """Application settings loaded from job.toml and environment variables.

    Precedence order:
    1. Environment variables (with JOB_ prefix)
    2. job.toml file (see _find_config_file for search order)
    3. Default values from schema

    Example environment variables:
        JOB_VERBOSE=true
        JOB_MODEL=gemini-2.5-flash
        JOB_DB_PATH=~/my-jobs.db
        JOB_FIT__CV=~/cv.md
    """

    # Top-level settings
    model: str | None = None
    verbose: bool = False
    db_path: str | None = Field(None, alias="db-path")

    # Nested configurations
    gh: JobGH = Field(default_factory=JobGH)
    fit: JobFit = Field(default_factory=JobFit)
    add: JobAdd = Field(default_factory=JobAdd)
    export: JobExport = Field(default_factory=JobExport)
    search: JobSearch = Field(default_factory=JobSearch)

    model_config = SettingsConfigDict(
        env_prefix="JOB_",
        env_nested_delimiter="__",
        extra="ignore",
        populate_by_name=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        """Customize settings sources to include TOML file."""
        config_file = _find_config_file()
        if config_file:
            # Use custom source that reads from [job] section
            return (
                init_settings,
                env_settings,
                _JobTomlSettingsSource(settings_cls, config_file),
            )
        return (init_settings, env_settings)

    # Application constants (not configurable)
    MIN_CONTENT_LENGTH: ClassVar[int] = 500
    PLAYWRIGHT_TIMEOUT_MS: ClassVar[int] = 30000
    REQUEST_TIMEOUT: ClassVar[int] = 15
    SYSTEM_PROMPT: ClassVar[str] = """
You extract structured job posting information from raw job ad text.

Rules:
- Always return valid JSON matching the schema.
- If a field is not explicitly mentioned, return an empty string.
- Do not invent facts.
- deadline must be ISO format (YYYY-MM-DD) or empty string.
"""

    def get_db_path(self) -> Path:
        """Get database path with proper resolution.

        Priority: config > env var > XDG default
        """
        if self.db_path:
            return Path(self.db_path).expanduser()

        if env_path := os.getenv("JOB_DB_PATH"):
            return Path(env_path).expanduser()

        # XDG-compliant default
        data_home = os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")
        db_dir = Path(data_home) / "job"
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "jobs.db"

    def get_model(self, override: str | None = None) -> str:
        """Get AI model with precedence: override > config > env > default."""
        return override or self.model or os.getenv("JOB_MODEL", "gemini-2.5-flash")


class _JobTomlSettingsSource:
    """Custom settings source that reads from [job] section in TOML."""

    def __init__(self, settings_cls: type[BaseSettings], toml_file: Path):
        self.settings_cls = settings_cls
        self.toml_file = toml_file

    def __call__(self) -> dict:
        """Load settings from [job] section."""
        import tomllib

        with open(self.toml_file, "rb") as f:
            data = tomllib.load(f)

        # Extract from [job] section if it exists
        return data.get("job", {})


def _find_config_file() -> Path | None:
    """Find job.toml in standard locations.

    Search order:
    1. JOB_CONFIG environment variable
    2. ./job.toml (current directory)
    3. $XDG_CONFIG_HOME/job/job.toml or ~/.config/job/job.toml
    4. ~/.job.toml (home directory)

    Returns:
        First existing config file path, or None if not found.
    """
    # 1. Environment variable
    if env_path := os.getenv("JOB_CONFIG"):
        path = Path(env_path).expanduser()
        if path.exists():
            return path

    # 2. Current working directory
    path = Path.cwd() / "job.toml"
    if path.exists():
        return path

    # 3. XDG config directory
    config_home = os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")
    path = Path(config_home) / "job" / "job.toml"
    if path.exists():
        return path

    # 4. User home directory
    path = Path.home() / ".job.toml"
    if path.exists():
        return path

    # No config file found
    return None


# Global settings instance
settings = Settings()
