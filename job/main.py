# main.py
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse

import typer

from dotenv import load_dotenv
from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry, UnexpectedModelBehavior
from sqlmodel import Session, select

from job.__version__ import __version__ as job_version
from job.core import AppContext, Config, JobAd, JobAdBase
from job.fetchers import BrowserFetcher, StaticFetcher

# Load environment variables from multiple locations (first found wins)
_env_locations = [
    Path.home() / ".config" / "job" / ".env",  # XDG-style config
    Path.home() / ".job.env",  # Home directory dotfile
    Path.cwd() / ".env",  # Current directory (for development)
]

for _env_path in _env_locations:
    if _env_path.exists():
        load_dotenv(_env_path)
        break
else:
    # Fallback: try default behavior (CWD)
    load_dotenv()

# -------------------------
# CLI App
# -------------------------
app = typer.Typer(
    invoke_without_command=True,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def error(message: str) -> None:
    """Print an error message to stderr."""
    typer.echo(f"Error: {message}", err=True)


# -------------------------
# AI Agent
# -------------------------


@lru_cache(maxsize=4)
def create_agent(model: str, system_prompt: str) -> Agent:
    """Create and cache an AI agent for the given model."""
    return Agent(
        model=model,
        output_type=JobAdBase,
        system_prompt=system_prompt,
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
# Fetching Strategy
# -------------------------
def fetch_job_text(url: str, ctx: AppContext) -> str:
    """Fetch job posting text, using browser if needed for JS-rendered content."""
    static_fetcher = StaticFetcher(
        timeout=ctx.config.REQUEST_TIMEOUT, logger=ctx.logger
    )

    try:
        text = static_fetcher.fetch(url)
        if len(text) >= ctx.config.MIN_CONTENT_LENGTH:
            ctx.logger.debug(f"Got {len(text)} chars from static fetch")
            return text
    except Exception:
        pass

    typer.echo("Page requires JavaScript, using browser...", err=True)
    browser_fetcher = BrowserFetcher(
        timeout_ms=ctx.config.PLAYWRIGHT_TIMEOUT_MS, logger=ctx.logger
    )
    return browser_fetcher.fetch(url)


def extract_job_info(url: str, job_text: str, ctx: AppContext) -> JobAdBase:
    """Extract job information using AI agent with error handling."""
    agent = create_agent(ctx.config.model, ctx.config.SYSTEM_PROMPT)

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


def version_option_callback(value: bool):
    if value:
        print(job_version)
        raise typer.Exit()


version_option = typer.Option(
    "--version",
    "-V",
    callback=version_option_callback,
    is_eager=True,
    help="Show version.",
)


@app.callback(epilog="Made with :purple_heart: in [bold blue]Copenhagen[/bold blue].")
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose/debug output"
    ),
    version: Annotated[bool | None, version_option] = None,
) -> None:
    """Job CLI - manage job postings."""
    config = Config.from_env(verbose=verbose)
    ctx.obj = AppContext(config=config)


@app.command()
def add(
    ctx: typer.Context,
    url_arg: str = typer.Argument(None, help="Job posting URL"),
    url: str = typer.Option(
        None, "--url", "-u", help="Job posting URL (takes precedence)"
    ),
    model: str = typer.Option(None, "--model", "-m", help="AI model to use"),
    no_cache: bool = typer.Option(
        False, "--no-cache", help="Bypass cache and always call the AI agent"
    ),
) -> None:
    """
    Add a job ad. Full job text is scraped and stored in the database.
    """
    app_ctx: AppContext = ctx.obj
    if model:
        # Override model if specified
        app_ctx = AppContext(
            config=Config.from_env(verbose=app_ctx.config.verbose, model=model)
        )

    final_url = url or url_arg
    if not final_url:
        error("URL is required.")
        raise typer.Exit(1)

    final_url = validate_url(final_url)
    app_ctx.logger.debug(f"Processing URL: {final_url}")

    # Check for existing entry (unless --no-cache is used)
    existing = None
    with Session(app_ctx.engine) as session:
        existing = session.exec(
            select(JobAd).where(JobAd.job_posting == final_url)
        ).first()

        if existing and not no_cache:
            typer.echo("Job already exists in database:")
            typer.echo(existing.model_dump_json(indent=2))
            return

    job_text = fetch_job_text(final_url, app_ctx)
    app_ctx.logger.debug(f"Fetched {len(job_text)} characters of job text")

    job_info = extract_job_info(final_url, job_text, app_ctx)

    # Convert AI output to database model, ensuring job_posting is the URL
    job_data = job_info.model_dump()
    job_data["job_posting"] = final_url  # Always use the actual URL

    with Session(app_ctx.engine) as session:
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
    ctx: typer.Context,
    url_arg: str = typer.Argument(..., help="Job posting URL to update"),
    model: str = typer.Option(None, "--model", "-m", help="AI model to use"),
) -> None:
    """
    Update an existing job ad by re-fetching and re-extracting.
    """
    app_ctx: AppContext = ctx.obj
    if model:
        app_ctx = AppContext(
            config=Config.from_env(verbose=app_ctx.config.verbose, model=model)
        )

    final_url = validate_url(url_arg)
    app_ctx.logger.debug(f"Updating job: {final_url}")

    with Session(app_ctx.engine) as session:
        existing = session.exec(
            select(JobAd).where(JobAd.job_posting == final_url)
        ).first()

        if not existing:
            error(f"No job found with URL: {final_url}")
            raise typer.Exit(1)

    # Re-fetch and update
    job_text = fetch_job_text(final_url, app_ctx)
    job_info = extract_job_info(final_url, job_text, app_ctx)
    job_data = job_info.model_dump()
    job_data["job_posting"] = final_url

    with Session(app_ctx.engine) as session:
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
