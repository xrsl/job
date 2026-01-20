# commands.py
import csv
import json
import sys
from io import StringIO
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


@app.command()
def export(
    ctx: typer.Context,
    identifier: str = typer.Argument(None, help="Job ID or URL to export (optional)"),
    format: str = typer.Option(
        "json", "--format", "-f", help="Export format: json or csv"
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
    query: str = typer.Option(None, "--query", "-q", help="Filter by search query"),
) -> None:
    """Export jobs to JSON or CSV format.

    If an identifier (ID or URL) is provided, exports only that job.
    Otherwise, exports all jobs (optionally filtered by --query).
    """
    app_ctx: AppContext = ctx.obj
    format = format.lower()

    if format not in ("json", "csv"):
        error(f"Unsupported format: {format}. Use 'json' or 'csv'.")
        raise typer.Exit(1)

    with Session(app_ctx.engine) as session:
        if identifier:
            # Export single job by ID or URL
            job = get_job_by_id_or_url(session, identifier)
            if not job:
                error(f"No job found with ID or URL matching: {identifier}")
                raise typer.Exit(1)
            jobs = [job]
        else:
            # Export all or query
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

    app_ctx.logger.debug(f"Exporting {len(jobs)} jobs as {format}")

    if format == "json":
        data = [job.model_dump() for job in jobs]
        content = json.dumps(data, indent=2, ensure_ascii=False)
    else:  # csv
        buffer = StringIO()
        fieldnames = [
            "id",
            "job_posting_url",
            "title",
            "company",
            "location",
            "deadline",
            "department",
            "hiring_manager",
            "job_ad",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fieldnames)
        writer.writeheader()
        for job in jobs:
            writer.writerow(job.model_dump())
        content = buffer.getvalue()

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
