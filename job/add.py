import json
import re
import subprocess
import typer
from functools import cache
from sqlmodel import Session, select
from rich.console import Console
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry, UnexpectedModelBehavior
from pydantic import ValidationError

from job.core import AppContext, JobAd, JobAdBase
from job.utils import error, validate_url
from job.fetchers import BrowserFetcher, StaticFetcher
from job.fetchers.base import FetchResult

console = Console()

# Create sub-app for add commands
app = typer.Typer()


@cache
def create_agent(model: str, system_prompt: str) -> Agent[None, JobAdBase]:
    """Create and cache an AI agent for the given model."""
    return Agent(
        model=model,
        output_type=JobAdBase,
        system_prompt=system_prompt,
    )


def fetch_job_text(url: str, ctx: AppContext, use_browser: bool = False) -> FetchResult:
    """Fetch job posting text with automatic fallback.

    Args:
        url: The URL to fetch
        ctx: Application context
        use_browser: If True, skip static fetch and use browser directly.
                     If False, try static first, fall back to browser on failure.

    Returns:
        FetchResult containing text and title
    """
    if use_browser:
        # Force browser fetch
        browser_fetcher = BrowserFetcher(
            timeout_ms=ctx.config.PLAYWRIGHT_TIMEOUT_MS,
            wait_time_ms=2000,
            logger=ctx.logger,
        )
        if ctx.config.verbose:
            console.log("[dim]Fetching with browser...[/dim]")
        return browser_fetcher.fetch(url)

    # Try static fetch first (fast)
    static_fetcher = StaticFetcher(
        timeout=ctx.config.REQUEST_TIMEOUT, logger=ctx.logger
    )
    if ctx.config.verbose:
        console.log("[dim]Fetching with requests...[/dim]")
    try:
        return static_fetcher.fetch(url)
    except Exception as e:
        # Static fetch failed, retry with browser
        ctx.logger.debug("static_fetch_failed", error=str(e))
        if ctx.config.verbose:
            console.log("[dim]Static fetch failed, retrying with browser...[/dim]")
        browser_fetcher = BrowserFetcher(
            timeout_ms=ctx.config.PLAYWRIGHT_TIMEOUT_MS,
            wait_time_ms=2000,
            logger=ctx.logger,
        )
        return browser_fetcher.fetch(url)


def extract_job_info(
    url: str, job_text: str, ctx: AppContext, model: str | None = None
) -> JobAdBase:
    """Extract job information using AI agent with error handling."""
    model_name = ctx.config.get_model(model)
    agent = create_agent(model_name, ctx.config.SYSTEM_PROMPT)

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
    url: str,
    fetch_result: FetchResult,
    structured: bool,
    ctx: AppContext,
    model: str | None = None,
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
        model_name = ctx.config.get_model(model)
        with console.status(
            f"[bold dim]Extracting fields using {model_name}...[/bold dim]"
        ):
            job_info = extract_job_info(url, job_text, ctx, model=model_name)
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


def fetch_github_issue(issue_number: int, ctx: AppContext) -> dict:
    """Fetch GitHub issue details using gh CLI.

    Args:
        issue_number: The GitHub issue number
        ctx: Application context

    Returns:
        Dict with issue data (title, body, url, etc.)

    Raises:
        typer.Exit: If issue fetch fails
    """
    try:
        result = subprocess.run(
            [
                "gh",
                "issue",
                "view",
                str(issue_number),
                "--json",
                "title,body,url,author",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            error(f"Failed to fetch GitHub issue {issue_number}: {result.stderr}")
            raise typer.Exit(1)

        issue_data = json.loads(result.stdout.strip())
        return issue_data

    except json.JSONDecodeError as e:
        error(f"Failed to parse GitHub issue JSON: {e}")
        raise typer.Exit(1)
    except FileNotFoundError:
        error("gh CLI not found. Please install GitHub CLI (gh) and authenticate")
        raise typer.Exit(1)


def parse_job_from_issue_body(body: str) -> dict:
    """Parse job data from GitHub issue body.

    The issue body is expected to be in the format created by 'job gh issue'.

    Args:
        body: The issue body text

    Returns:
        Dict with extracted job data
    """
    # Extract fields using regex patterns
    patterns = {
        "company": r"\*\*Company:\*\*\s*(.+)",
        "location": r"\*\*Location:\*\*\s*(.+)",
        "department": r"\*\*Department:\*\*\s*(.+)",
        "deadline": r"\*\*Deadline:\*\*\s*(.+)",
        "hiring_manager": r"\*\*Hiring Manager:\*\*\s*(.+)",
        "job_posting_url": r"\*\*Job Posting:\*\*\s*(.+)",
    }

    job_data = {}
    for field, pattern in patterns.items():
        match = re.search(pattern, body, re.MULTILINE)
        if match:
            value = match.group(1).strip()
            # Convert "N/A" to empty string
            job_data[field] = "" if value == "N/A" else value
        else:
            job_data[field] = ""

    # Extract full job description (everything after "## Full Job Description")
    full_ad_match = re.search(r"## Full Job Description\s*\n\n(.+)", body, re.DOTALL)
    if full_ad_match:
        job_data["full_ad"] = full_ad_match.group(1).strip()
    else:
        # Fallback: use the entire body as full_ad
        job_data["full_ad"] = body.strip()

    return job_data


def _build_job_data_from_issue(
    issue_number: int,
    structured: bool,
    ctx: AppContext,
    model: str | None = None,
) -> dict:
    """Build job data dict from GitHub issue.

    Args:
        issue_number: GitHub issue number
        structured: If True, use AI to extract structured fields
        ctx: Application context

    Returns:
        Dict with job data ready for database insertion
    """
    # Fetch issue data
    with console.status(
        f"[bold dim]Fetching GitHub issue #{issue_number}...[/bold dim]"
    ):
        issue_data = fetch_github_issue(issue_number, ctx)

    title = issue_data["title"]
    body = issue_data["body"]
    issue_url = issue_data["url"]

    # Parse job data from issue body
    job_data = parse_job_from_issue_body(body)

    # Set title from issue title if not found in body
    if not job_data.get("title"):
        job_data["title"] = title

    # If structured extraction is requested, use AI to refine the data
    if structured:
        model_name = ctx.config.get_model(model)
        with console.status(
            f"[bold dim]Extracting fields using {model_name}...[/bold dim]"
        ):
            # Create a combined text for AI extraction
            combined_text = f"Title: {title}\n\n{body}"
            job_info = extract_job_info(issue_url, combined_text, ctx, model=model_name)
            # Merge AI-extracted data with parsed data
            ai_data = job_info.model_dump()
            ai_data["job_posting_url"] = job_data.get("job_posting_url", issue_url)
            # Keep original full_ad from issue
            ai_data["full_ad"] = job_data["full_ad"]
            job_data = ai_data
    else:
        # Ensure required fields are set
        job_data.setdefault("job_posting_url", issue_url)

    return job_data


@app.command(name="a", hidden=True)
@app.command(name="add")
def add(
    ctx: typer.Context,
    url: str = typer.Argument(None, help="Job posting URL"),
    from_issue: int = typer.Option(
        None, "--from-issue", "-i", help="GitHub issue number to create job from"
    ),
    structured: bool = typer.Option(
        None,
        "--structured",
        "-s",
        help="Use AI to extract structured fields (from config if not specified)",
    ),
    model: str = typer.Option(
        None, "--model", "-m", help="AI model to use (from config if not specified)"
    ),
    browser: bool = typer.Option(
        None,
        "--browser",
        "-b",
        help="Use browser automation to fetch the page (from config if not specified)",
    ),
) -> None:
    """
    Add or update a job ad. (Alias: a)

    Fetches the job posting and stores it in the database.
    If the job already exists (same URL), it will be updated with fresh data.
    By default, uses fast static fetching (requests).
    Use --browser to use a full browser (Playwright) for JS-heavy sites.
    Use --structured to extract structured fields (title, company, etc.) via AI.
    Use --from-issue to create a job from an existing GitHub issue.

    Examples:
        job add https://example.com/job
        job add https://example.com/job --structured
        job add https://example.com/job  # uses defaults from job.toml
        job add --from-issue 45
    """
    app_ctx: AppContext = ctx.obj

    # Validate that either url or from_issue is provided, but not both
    if url and from_issue:
        error("Cannot specify both URL and --from-issue")
        raise typer.Exit(1)
    if not url and not from_issue:
        error("Must specify either URL or --from-issue")
        raise typer.Exit(1)

    # Use config defaults if flags not explicitly provided
    final_structured = (
        structured if structured is not None else app_ctx.config.add.structured
    )
    final_browser = browser if browser is not None else app_ctx.config.add.browser
    final_model = app_ctx.config.get_model(model or app_ctx.config.add.model)

    if from_issue:
        # Handle GitHub issue case
        app_ctx.logger.debug(f"Processing GitHub issue: {from_issue}")
        job_data = _build_job_data_from_issue(
            from_issue, final_structured, app_ctx, model=final_model
        )
        final_url = job_data["job_posting_url"]  # Extract URL from issue
    else:
        # Handle URL case
        final_url = validate_url(url)
        app_ctx.logger.debug(f"Processing URL: {final_url}")

        # Fetch job content
        with console.status("[bold dim]Fetching job page...[/bold dim]"):
            fetch_result = fetch_job_text(final_url, app_ctx, use_browser=final_browser)
        app_ctx.logger.debug("job_text_fetched", chars=len(fetch_result.content))

        job_data = _build_job_data(
            final_url, fetch_result, final_structured, app_ctx, model=final_model
        )

    with Session(app_ctx.engine) as session:
        # Check for existing entry
        existing = session.exec(
            select(JobAd).where(JobAd.job_posting_url == final_url)
        ).first()

        if existing:
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
