# search_config.py
"""
TOML-based configuration for job search career pages.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib


@dataclass
class CareerPage:
    """A career page to search for job listings."""

    company: str
    url: str
    keywords: list[str] = field(default_factory=list)
    enabled: bool = True

    def __str__(self) -> str:
        return f"{self.company} ({self.url})"


@dataclass
class SearchConfig:
    """Configuration for job search."""

    pages: list[CareerPage]
    default_keywords: list[str]
    config_path: Path

    @property
    def enabled_pages(self) -> list[CareerPage]:
        """Return only enabled pages."""
        return [p for p in self.pages if p.enabled]

    def get_keywords_for_page(self, page: CareerPage) -> list[str]:
        """Get keywords for a page (page-specific or defaults)."""
        return page.keywords if page.keywords else self.default_keywords


def get_config_path() -> Path:
    """Get the config file path. Checks multiple locations."""
    # 1. Environment variable
    if env_path := os.getenv("JOB_SEARCH_CONFIG"):
        return Path(env_path).expanduser()

    # 2. Current working directory
    cwd_path = Path.cwd() / "job-search.toml"
    if cwd_path.exists():
        return cwd_path

    # 3. XDG config directory
    config_home = os.getenv("XDG_CONFIG_HOME", Path.home() / ".config")
    xdg_path = Path(config_home) / "job" / "job-search.toml"
    if xdg_path.exists():
        return xdg_path

    # 4. User home directory
    home_path = Path.home() / ".job-search.toml"
    if home_path.exists():
        return home_path

    # Default to cwd if nothing found
    return cwd_path


def load_config(config_path: Path | None = None) -> SearchConfig:
    """
    Load the search configuration from TOML file.

    Args:
        config_path: Optional explicit path. If None, searches standard locations.

    Returns:
        SearchConfig with parsed pages and keywords.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ValueError: If config file is invalid.
    """
    path = config_path or get_config_path()

    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Create one at one of these locations:\n"
            f"  - ./job-search.toml (current directory)\n"
            f"  - ~/.config/job/job-search.toml\n"
            f"  - ~/.job-search.toml\n"
            f"  - Set JOB_SEARCH_CONFIG environment variable"
        )

    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML in {path}: {e}") from e

    # Parse keywords from job.search section
    job_search = data.get("job", {}).get("search", {})
    default_keywords = job_search.get("keywords", [])

    # Parse career pages
    pages_data = data.get("job", {}).get("search", {}).get("in", [])
    pages = []

    for i, page_data in enumerate(pages_data):
        if "company" not in page_data:
            raise ValueError(f"Page {i + 1} missing required field 'company'")
        if "url" not in page_data:
            raise ValueError(
                f"Page '{page_data['company']}' missing required field 'url'"
            )

        pages.append(
            CareerPage(
                company=page_data["company"],
                url=page_data["url"],
                keywords=page_data.get("keywords", []),
                enabled=page_data.get("enabled", True),
            )
        )

    return SearchConfig(
        pages=pages,
        default_keywords=default_keywords,
        config_path=path,
    )
