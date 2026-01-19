# main.py
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import requests
import typer
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry, UnexpectedModelBehavior
from sqlmodel import Field, Session, SQLModel, create_engine, select

load_dotenv()

# -------------------------
# CLI App
# -------------------------
app = typer.Typer(
    invoke_without_command=True,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Global state for verbose mode
_verbose = False


def log(message: str, err: bool = False) -> None:
    """Log a message if verbose mode is enabled."""
    if _verbose:
        typer.echo(f"[DEBUG] {message}", err=err)


def error(message: str) -> None:
    """Print an error message to stderr."""
    typer.echo(f"Error: {message}", err=True)


# -------------------------
# Database model
# -------------------------
class JobAdBase(SQLModel):
    """Base schema for AI extraction (no DB metadata)."""

    job_posting: str
    title: str
    company: str
    location: str
    deadline: str
    department: str
    hiring_manager: str
    job_ad: str


class JobAd(JobAdBase, table=True):
    """Database table model."""

    id: int | None = Field(default=None, primary_key=True)
    job_posting: str = Field(index=True, unique=True)


# -------------------------
# Database setup (lazy initialization)
# -------------------------
_engine = None


def get_db_path() -> Path:
    """Get database path from env or use default XDG-compliant location."""
    if env_path := os.getenv("JOB_DB_PATH"):
        return Path(env_path).expanduser()

    # XDG-compliant default: ~/.local/share/job/jobs.db
    data_home = os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share")
    db_dir = Path(data_home) / "job"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "jobs.db"


def get_engine():
    """Lazy initialization of database engine."""
    global _engine
    if _engine is None:
        db_path = get_db_path()
        log(f"Using database: {db_path}")
        _engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(_engine)
    return _engine


# -------------------------
# Constants
# -------------------------
DEFAULT_MODEL = os.getenv("JOB_MODEL", "gemini-2.5-flash")
MIN_CONTENT_LENGTH = 500
PLAYWRIGHT_TIMEOUT_MS = 30000  # 30 seconds
REQUEST_TIMEOUT = 15  # seconds

SYSTEM_PROMPT = """
You extract structured job posting information from raw job ad text.

Rules:
- Always return valid JSON matching the schema.
- If a field is not explicitly mentioned, return an empty string.
- Do not invent facts.
- deadline must be ISO format (YYYY-MM-DD) or empty string.
"""


@lru_cache(maxsize=4)
def create_agent(model: str) -> Agent:
    """Create and cache an AI agent for the given model."""
    log(f"Creating agent with model: {model}")
    return Agent(
        model=model,
        output_type=JobAdBase,
        system_prompt=SYSTEM_PROMPT,
    )


# -------------------------
# Validation
# -------------------------
def validate_url(url: str) -> str:
    """Validate and normalize a URL. Raises typer.Exit on invalid URL."""
    url = url.strip()

    # Add scheme if missing
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            error(f"Invalid URL: missing domain in '{url}'")
            raise typer.Exit(1)
        if parsed.scheme not in ("http", "https"):
            error(f"Invalid URL scheme: '{parsed.scheme}' (must be http or https)")
            raise typer.Exit(1)
        # Check for valid domain (must have a dot for TLD, unless localhost)
        if "." not in parsed.netloc and "localhost" not in parsed.netloc.lower():
            error(f"Invalid domain: '{parsed.netloc}' (missing TLD)")
            raise typer.Exit(1)
        return url
    except ValueError as e:
        error(f"Invalid URL format: {e}")
        raise typer.Exit(1)


# -------------------------
# Helpers
# -------------------------
def _ensure_browser_installed() -> None:
    """Ensure Playwright browser is installed."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception as e:
        log(f"Browser not available: {e}")
        typer.echo("Installing browser (first-time setup)...", err=True)
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            error(f"Failed to install browser: {result.stderr}")
            raise typer.Exit(1)


def _fetch_with_requests(url: str) -> str:
    """Fetch page content using requests (for static pages)."""
    log(f"Fetching with requests: {url}")
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        return soup.get_text(separator="\n", strip=True)
    except requests.Timeout:
        log(f"Request timed out after {REQUEST_TIMEOUT}s")
        return ""
    except requests.RequestException as e:
        log(f"Request failed: {e}")
        return ""


def _fetch_with_playwright(url: str) -> str:
    """Fetch page content using Playwright (for JavaScript-heavy pages)."""
    log(f"Fetching with Playwright: {url}")
    _ensure_browser_installed()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=PLAYWRIGHT_TIMEOUT_MS)
            # Wait for dynamic content to load (career pages often load jobs via JS)
            page.wait_for_timeout(8000)
            text = page.inner_text("body")
            browser.close()
            return text
    except PlaywrightTimeout:
        error(f"Page load timed out after {PLAYWRIGHT_TIMEOUT_MS // 1000}s")
        raise typer.Exit(1)
    except Exception as e:
        error(f"Browser fetch failed: {e}")
        raise typer.Exit(1)


def fetch_job_text(url: str) -> str:
    """Fetch job posting text, using browser if needed for JS-rendered content."""
    text = _fetch_with_requests(url)
    if len(text) >= MIN_CONTENT_LENGTH:
        log(f"Got {len(text)} chars from static fetch")
        return text

    typer.echo("Page requires JavaScript, using browser...", err=True)
    return _fetch_with_playwright(url)


def extract_job_info(url: str, job_text: str, model: str) -> JobAdBase:
    """Extract job information using AI agent with error handling."""
    agent = create_agent(model)

    try:
        result = agent.run_sync(
            f"Extract job info from this posting.\nURL: {url}\n\nJob text:\n{job_text}"
        )
        return result.output
    except ValidationError as e:
        error(f"AI returned invalid data: {e}")
        raise typer.Exit(1)
    except UnexpectedModelBehavior as e:
        error(f"AI model behaved unexpectedly: {e}")
        raise typer.Exit(1)
    except ModelRetry as e:
        error(f"AI model failed after retries: {e}")
        raise typer.Exit(1)
    except Exception as e:
        error(f"Failed to extract job info: {e}")
        raise typer.Exit(1)


# -------------------------
# CLI
# -------------------------
@app.callback()
def main(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose/debug output"
    ),
) -> None:
    """Job CLI - manage job postings."""
    global _verbose
    _verbose = verbose
    if verbose:
        log("Verbose mode enabled")


@app.command()
def add(
    url_arg: str = typer.Argument(None, help="Job posting URL"),
    url: str = typer.Option(
        None, "--url", "-u", help="Job posting URL (takes precedence)"
    ),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="AI model to use"),
    no_cache: bool = typer.Option(
        False, "--no-cache", help="Bypass cache and always call the AI agent"
    ),
) -> None:
    """
    Add a job ad. Full job text is scraped and stored in the database.
    """
    final_url = url or url_arg
    if not final_url:
        error("URL is required.")
        raise typer.Exit(1)

    final_url = validate_url(final_url)
    log(f"Processing URL: {final_url}")

    # Check for existing entry (unless --no-cache is used)
    engine = get_engine()
    existing = None
    with Session(engine) as session:
        existing = session.exec(
            select(JobAd).where(JobAd.job_posting == final_url)
        ).first()

        if existing and not no_cache:
            typer.echo("Job already exists in database:")
            typer.echo(existing.model_dump_json(indent=2))
            return

    job_text = fetch_job_text(final_url)
    log(f"Fetched {len(job_text)} characters of job text")

    job_info = extract_job_info(final_url, job_text, model)

    # Convert AI output to database model, ensuring job_posting is the URL
    job_data = job_info.model_dump()
    job_data["job_posting"] = final_url  # Always use the actual URL

    with Session(engine) as session:
        if existing and no_cache:
            # Update existing entry
            for key, value in job_data.items():
                setattr(existing, key, value)
            session.add(existing)
            session.commit()
            session.refresh(existing)
            typer.echo("Job updated:")
            typer.echo(existing.model_dump_json(indent=2))
        else:
            # Create new entry
            job = JobAd.model_validate(job_data)
            session.add(job)
            session.commit()
            session.refresh(job)
            typer.echo("Job saved:")
            typer.echo(job.model_dump_json(indent=2))


@app.command()
def update(
    url_arg: str = typer.Argument(..., help="Job posting URL to update"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="AI model to use"),
) -> None:
    """
    Update an existing job ad by re-fetching and re-extracting.
    """
    final_url = validate_url(url_arg)
    log(f"Updating job: {final_url}")

    engine = get_engine()
    with Session(engine) as session:
        existing = session.exec(
            select(JobAd).where(JobAd.job_posting == final_url)
        ).first()

        if not existing:
            error(f"No job found with URL: {final_url}")
            raise typer.Exit(1)

    # Re-fetch and update
    job_text = fetch_job_text(final_url)
    job_info = extract_job_info(final_url, job_text, model)
    job_data = job_info.model_dump()
    job_data["job_posting"] = final_url

    with Session(engine) as session:
        existing = session.exec(
            select(JobAd).where(JobAd.job_posting == final_url)
        ).first()
        assert existing is not None  # Already validated above
        for key, value in job_data.items():
            setattr(existing, key, value)
        session.add(existing)
        session.commit()
        session.refresh(existing)
        typer.echo("Job updated:")
        typer.echo(existing.model_dump_json(indent=2))


# Import commands to register them with the app
from job import commands  # noqa: E402, F401
from job import search  # noqa: E402, F401

if __name__ == "__main__":
    app()
