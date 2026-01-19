"""Centralized application configuration."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final


@dataclass(frozen=True)
class Config:
    """Application configuration with environment variable support."""

    model: str
    db_path: Path
    search_config_path: Path | None
    verbose: bool = False

    # Constants
    MIN_CONTENT_LENGTH: Final[int] = 500
    PLAYWRIGHT_TIMEOUT_MS: Final[int] = 30000
    REQUEST_TIMEOUT: Final[int] = 15
    SYSTEM_PROMPT: Final[str] = """
You extract structured job posting information from raw job ad text.

Rules:
- Always return valid JSON matching the schema.
- If a field is not explicitly mentioned, return an empty string.
- Do not invent facts.
- deadline must be ISO format (YYYY-MM-DD) or empty string.
"""

    @classmethod
    def from_env(cls, verbose: bool = False, model: str | None = None) -> "Config":
        """Create configuration from environment variables."""
        return cls(
            model=model or os.getenv("JOB_MODEL", "gemini-2.5-flash"),
            db_path=cls._get_db_path(),
            search_config_path=None,
            verbose=verbose,
        )

    @staticmethod
    def _get_db_path() -> Path:
        """Get database path from env or use default XDG-compliant location."""
        if env_path := os.getenv("JOB_DB_PATH"):
            return Path(env_path).expanduser()

        # XDG-compliant default: ~/.local/share/job/jobs.db
        data_home = os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")
        db_dir = Path(data_home) / "job"
        db_dir.mkdir(parents=True, exist_ok=True)
        return db_dir / "jobs.db"
