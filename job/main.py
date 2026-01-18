# main.py
import subprocess
import sys

import requests
from bs4 import BeautifulSoup
import typer
from pydantic_ai import Agent
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from sqlmodel import SQLModel, Field, create_engine, Session, select

load_dotenv()

app = typer.Typer(invoke_without_command=True, no_args_is_help=True)

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
# Database setup
# -------------------------
engine = create_engine("sqlite:///jobs.db")
SQLModel.metadata.create_all(engine)


# -------------------------
# Constants
# -------------------------
DEFAULT_MODEL = "gemini-2.5-flash"
MIN_CONTENT_LENGTH = 500

SYSTEM_PROMPT = """
You extract structured job posting information from raw job ad text.

Rules:
- Always return valid JSON matching the schema.
- If a field is not explicitly mentioned, return an empty string.
- Do not invent facts.
- deadline must be ISO format (YYYY-MM-DD) or empty string.
"""


def create_agent(model: str) -> Agent:
    return Agent(
        model=model,
        output_type=JobAdBase,  # Use base model without DB metadata
        system_prompt=SYSTEM_PROMPT,
    )


# -------------------------
# Helpers
# -------------------------
def _ensure_browser_installed():
    try:
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
    except Exception:
        typer.echo("Installing browser (first-time setup)...", err=True)
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
        )


def _fetch_with_requests(url: str) -> str:
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def _fetch_with_playwright(url: str) -> str:
    _ensure_browser_installed()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(2000)
        text = page.inner_text("body")
        browser.close()
        return text


def fetch_job_text(url: str) -> str:
    text = _fetch_with_requests(url)
    if len(text) >= MIN_CONTENT_LENGTH:
        return text

    typer.echo("Page requires JavaScript, using browser...", err=True)
    return _fetch_with_playwright(url)


# -------------------------
# CLI
# -------------------------
@app.callback()
def main():
    """Job CLI - manage job postings."""
    pass


@app.command()
def add(
    url_arg: str = typer.Argument(None, help="Job posting URL"),
    url: str = typer.Option(None, "--url", "-u", help="Job posting URL (takes precedence)"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m", help="AI model to use"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Bypass cache and always call the AI agent"),
):
    """
    Add a job ad. Full job text is scraped and stored in the database.
    """
    final_url = url or url_arg
    if not final_url:
        typer.echo("Error: URL is required.", err=True)
        raise typer.Exit(1)

    # Check for existing entry (unless --no-cache is used)
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
    agent = create_agent(model)

    result = agent.run_sync(
        f"Extract job info from this posting.\nURL: {final_url}\n\nJob text:\n{job_text}"
    )

    # Convert AI output to database model, ensuring job_posting is the URL
    job_data = result.output.model_dump()
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

# Import commands to register them with the app
from job import commands  # noqa: F401

if __name__ == "__main__":
    app()
