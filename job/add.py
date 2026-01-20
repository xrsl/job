import typer
from functools import cache
from sqlmodel import Session, select
from rich.console import Console
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry, UnexpectedModelBehavior
from pydantic import ValidationError

from job.core import AppContext, Config, JobAd, JobAdBase
from job.cli_app import app
from job.utils import error, validate_url
from job.fetchers import BrowserFetcher, StaticFetcher
from job.fetchers.base import FetchResult

console = Console()


@cache
def create_agent(model: str, system_prompt: str) -> Agent[None, JobAdBase]:
    """Create and cache an AI agent for the given model."""
    return Agent(
        model=model,
        output_type=JobAdBase,
        system_prompt=system_prompt,
    )


def fetch_job_text(url: str, ctx: AppContext, use_browser: bool = False) -> FetchResult:
    """Fetch job posting text.

    Args:
        url: The URL to fetch
        ctx: Application context
        use_browser: If True, use BrowserFetcher (slower, handles JS).
                     If False, use StaticFetcher (fast, no JS).

    Returns:
        FetchResult containing text and title
    """
    if use_browser:
        # Use browser fetcher (Profile -> Fresh)
        browser_fetcher = BrowserFetcher(
            timeout_ms=ctx.config.PLAYWRIGHT_TIMEOUT_MS,
            wait_time_ms=2000,
            logger=ctx.logger,
        )
        console.log("[dim]Fetching with browser...[/dim]")
        return browser_fetcher.fetch(url)

    # Use static fetcher (default)
    static_fetcher = StaticFetcher(
        timeout=ctx.config.REQUEST_TIMEOUT, logger=ctx.logger
    )
    console.log("[dim]Fetching with requests...[/dim]")
    return static_fetcher.fetch(url)


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


def _build_job_data(
    url: str, fetch_result: FetchResult, structured: bool, ctx: AppContext
) -> dict:
    """Build job data dict, optionally using AI extraction.

    Args:
        url: The job posting URL
        fetch_result: The fetched job result including text and title
        structured: If True, use AI to extract structured fields
        ctx: Application context

    Returns:
        Dict with job data ready for database insertion
    """
    job_text = fetch_result.content
    if structured:
        job_info = extract_job_info(url, job_text, ctx)
        job_data = job_info.model_dump()
        job_data["job_posting_url"] = url
    else:
        title = fetch_result.title or ""
        job_data = {
            "job_posting_url": url,
            "title": title,
            "company": "",
            "location": "",
            "deadline": "",
            "department": "",
            "hiring_manager": "",
            "full_ad": job_text,
        }
    return job_data


@app.command(name="a", hidden=True)
@app.command()
def add(
    ctx: typer.Context,
    url: str = typer.Argument(..., help="Job posting URL"),
    structured: bool = typer.Option(
        False, "--structured", "-s", help="Use AI to extract structured fields"
    ),
    model: str = typer.Option(None, "--model", "-m", help="AI model to use"),
    browser: bool = typer.Option(
        False, "--browser", "-b", help="Use browser automation to fetch the page"
    ),
) -> None:
    """
    Add or update a job ad. (Alias: a)

    Fetches the job posting and stores it in the database.
    If the job already exists (same URL), it will be updated with fresh data.
    By default, uses fast static fetching (requests).
    Use --browser to use a full browser (Playwright) for JS-heavy sites.
    Use --structured to extract structured fields (title, company, etc.) via AI.
    """
    app_ctx: AppContext = ctx.obj
    if model:
        # Override model if specified
        app_ctx = AppContext(
            config=Config.from_env(verbose=app_ctx.config.verbose, model=model)
        )

    final_url = validate_url(url)
    app_ctx.logger.debug(f"Processing URL: {final_url}")

    # Check for existing entry
    with Session(app_ctx.engine) as session:
        existing = session.exec(
            select(JobAd).where(JobAd.job_posting_url == final_url)
        ).first()

    # Fetch job content
    with console.status("[bold dim]Fetching job page...[/bold dim]"):
        fetch_result = fetch_job_text(final_url, app_ctx, use_browser=browser)
    app_ctx.logger.debug("job_text_fetched", chars=len(fetch_result.content))

    job_data = _build_job_data(final_url, fetch_result, structured, app_ctx)

    with Session(app_ctx.engine) as session:
        if existing:
            # Update existing entry
            existing = session.exec(
                select(JobAd).where(JobAd.job_posting_url == final_url)
            ).first()
            assert existing is not None  # Already validated above
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
