# commands.py
import json
import sys
from typing import Sequence

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import Session, col, desc, select

from job.core import AppContext, JobAd
from job.main import app, error, validate_url

console = Console()


# -------------------------
# Table Formatting (DRY)
# -------------------------
def format_job_table(jobs: Sequence[JobAd]) -> None:
    """Format and print a list of jobs as a colorful Rich table."""
    if not jobs:
        return

    table = Table(show_header=True, header_style="bold cyan", border_style="dim")
    table.add_column("ID", style="dim", justify="right", no_wrap=True)
    table.add_column("Title", style="magenta", no_wrap=False)
    table.add_column("Company", style="green")
    table.add_column("URL", style="blue", no_wrap=False)

    for job in jobs:
        table.add_row(
            str(job.id),
            job.title or "",
            job.company or "",
            f"[link={job.job_posting_url}]{job.job_posting_url}[/link]"
            if job.job_posting_url
            else "",
        )

    console.print(table)


def get_job_by_id_or_url(session: Session, identifier: str) -> JobAd | None:
    """Find a job by ID (if integer) or URL."""
    if identifier.isdigit():
        job = session.get(JobAd, int(identifier))
        if job:
            return job

    # Fallback to URL lookup
    try:
        url = validate_url(identifier)
        return session.exec(select(JobAd).where(JobAd.job_posting_url == url)).first()
    except typer.Exit:
        # validate_url raises Exit on failure, but here we might just want to return None
        # if the identifier isn't a valid URL either.
        # However, validate_url prints an error before exiting.
        # To be safe, we can just let it raise if it looks like a URL but fails,
        # or we could catch it. Use simple string check first?
        return None


# -------------------------
# Commands
# -------------------------
@app.command(name="ls", hidden=True)
@app.command(name="list")
def list_jobs(ctx: typer.Context) -> None:
    """List all stored job ads. (Alias: ls)"""
    app_ctx: AppContext = ctx.obj
    with Session(app_ctx.engine) as session:
        jobs = session.exec(select(JobAd).order_by(desc(JobAd.id))).all()

    if not jobs:
        typer.echo("No jobs found.")
        return

    format_job_table(jobs)


@app.command()
def show(
    ctx: typer.Context,
    identifier: str = typer.Argument(..., help="Job ID or URL"),
) -> None:
    """Show a single job ad by ID or URL."""
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        job = get_job_by_id_or_url(session, identifier)

        if not job:
            # If get_job_by_id_or_url returned None (and didn't exit), it means not found
            error(f"No job found with ID or URL matching: {identifier}")
            raise typer.Exit(1)

        typer.echo(job.model_dump_json(indent=2))


@app.command()
def rm(
    ctx: typer.Context,
    identifier: str = typer.Argument(..., help="Job ID or URL"),
) -> None:
    """Delete a job ad by ID or URL."""
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        job = get_job_by_id_or_url(session, identifier)

        if not job:
            error(f"No job found with ID or URL matching: {identifier}")
            raise typer.Exit(1)

        url = job.job_posting_url
        session.delete(job)
        session.commit()

    typer.echo(f"Deleted job {job.id}: {url}")


@app.command()
def find(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search keywords"),
) -> None:
    """Find jobs in local database by keyword (title, company, department, location, body)."""
    app_ctx: AppContext = ctx.obj
    q = f"%{query.lower()}%"
    app_ctx.logger.debug(f"Searching for: {query}")

    with Session(app_ctx.engine) as session:
        jobs = session.exec(
            select(JobAd)
            .where(
                (col(JobAd.title).ilike(q))
                | (col(JobAd.company).ilike(q))
                | (col(JobAd.department).ilike(q))
                | (col(JobAd.location).ilike(q))
                | (col(JobAd.job_ad).ilike(q))
            )
            .order_by(desc(JobAd.id))
        ).all()

    if not jobs:
        typer.echo("No matching jobs found.")
        return

    app_ctx.logger.debug(f"Found {len(jobs)} matching jobs")
    format_job_table(jobs)


@app.command(name="e", hidden=True)
@app.command(name="export")
def export(
    ctx: typer.Context,
    job_ids: list[int] = typer.Option(None, "--id", "-i", help="Job ID(s) to export"),
    urls: list[str] = typer.Option(None, "--url", "-u", help="Job URL(s) to export"),
    output: str = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
    query: str = typer.Option(None, "--query", "-q", help="Filter by search query"),
) -> None:
    """Export jobs to JSON format.

    Export specific jobs by ID or URL (repeatable flags), or all jobs matching a query.
    Examples:
        job e --id 1 --id 2
        job export --url https://example.com --id 5
        job e -q "python"
    """
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        jobs = []

        # 1. Fetch by explicit IDs/URLs if provided
        if job_ids or urls:
            # IDs
            if job_ids:
                for jid in job_ids:
                    job = session.get(JobAd, jid)
                    if job:
                        jobs.append(job)
                    else:
                        error(f"No job found with ID: {jid}")

            # URLs
            if urls:
                for url in urls:
                    url_clean = validate_url(url)
                    job = session.exec(
                        select(JobAd).where(JobAd.job_posting_url == url_clean)
                    ).first()
                    if job:
                        # Avoid duplicates if ID and URL point to same job
                        if job not in jobs:
                            jobs.append(job)
                    else:
                        error(f"No job found with URL: {url}")

            if not jobs:
                # If arguments were provided but nothing found, we should probably exit
                # But errors are already printed.
                raise typer.Exit(1)

        # 2. If no explicit IDs/URLs, use query or all
        else:
            stmt = select(JobAd).order_by(desc(JobAd.id))

            if query:
                q = f"%{query.lower()}%"
                stmt = stmt.where(
                    (col(JobAd.title).ilike(q))
                    | (col(JobAd.company).ilike(q))
                    | (col(JobAd.department).ilike(q))
                    | (col(JobAd.location).ilike(q))
                    | (col(JobAd.job_ad).ilike(q))
                )

            jobs = session.exec(stmt).all()

    if not jobs:
        typer.echo("No jobs to export.")
        return

    app_ctx.logger.debug(f"Exporting {len(jobs)} jobs as json")

    data = [job.model_dump() for job in jobs]
    content = json.dumps(data, indent=2, ensure_ascii=False)

    if output:
        try:
            with open(output, "w", encoding="utf-8") as f:
                f.write(content)
            typer.echo(f"Exported {len(jobs)} jobs to {output}")
        except OSError as e:
            error(f"Failed to write file: {e}")
            raise typer.Exit(1)
    else:
        # Write to stdout
        sys.stdout.write(content)
        if not content.endswith("\n"):
            sys.stdout.write("\n")


@app.command(name="dbinfo")
def dbinfo(ctx: typer.Context) -> None:
    """Show database location and statistics."""
    app_ctx: AppContext = ctx.obj
    db_path = app_ctx.config.db_path

    with Session(app_ctx.engine) as session:
        count = len(session.exec(select(JobAd)).all())

    typer.echo(f"Database: {db_path}")
    typer.echo(f"Total jobs: {count}")

    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        typer.echo(f"Database size: {size_kb:.1f} KB")
