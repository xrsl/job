# commands.py
import csv
import json
import sys
from io import StringIO
from typing import Sequence

import typer
from sqlmodel import Session, col, desc, select

from job.core import AppContext, JobAd
from job.main import app, error, validate_url


# -------------------------
# Table Formatting (DRY)
# -------------------------
def format_job_table(jobs: Sequence[JobAd]) -> str:
    """Format a list of jobs as a table string."""
    if not jobs:
        return ""

    # Calculate column widths
    url_w = max(len("URL"), max(len(j.job_posting or "") for j in jobs))
    title_w = max(len("TITLE"), max(len(j.title or "") for j in jobs))
    company_w = max(len("COMPANY"), max(len(j.company or "") for j in jobs))
    location_w = max(len("LOCATION"), max(len(j.location or "") for j in jobs))

    lines = []
    # Header
    lines.append(
        f"{'TITLE':<{title_w}}  {'COMPANY':<{company_w}}  "
        f"{'LOCATION':<{location_w}}  {'URL':<{url_w}}"
    )

    # Rows
    for job in jobs:
        lines.append(
            f"{(job.title or ''):<{title_w}}  {(job.company or ''):<{company_w}}  "
            f"{(job.location or ''):<{location_w}}  {(job.job_posting or ''):<{url_w}}"
        )

    return "\n".join(lines)


# -------------------------
# Commands
# -------------------------
@app.command(name="list")
def list_jobs(ctx: typer.Context) -> None:
    """List all stored job ads."""
    app_ctx: AppContext = ctx.obj
    with Session(app_ctx.engine) as session:
        jobs = session.exec(select(JobAd).order_by(desc(JobAd.id))).all()

    if not jobs:
        typer.echo("No jobs found.")
        return

    typer.echo(format_job_table(jobs))


@app.command()
def show(
    ctx: typer.Context, url: str = typer.Argument(..., help="Job posting URL")
) -> None:
    """Show a single job ad by URL."""
    app_ctx: AppContext = ctx.obj
    url = validate_url(url)

    with Session(app_ctx.engine) as session:
        job = session.exec(select(JobAd).where(JobAd.job_posting == url)).first()

    if not job:
        error(f"No job found with url={url}")
        raise typer.Exit(1)

    typer.echo(job.model_dump_json(indent=2))


@app.command()
def rm(
    ctx: typer.Context, url: str = typer.Argument(..., help="Job posting URL")
) -> None:
    """Delete a job ad by URL."""
    app_ctx: AppContext = ctx.obj
    url = validate_url(url)

    with Session(app_ctx.engine) as session:
        job = session.exec(select(JobAd).where(JobAd.job_posting == url)).first()
        if not job:
            error(f"No job found with url={url}")
            raise typer.Exit(1)

        session.delete(job)
        session.commit()

    typer.echo(f"Deleted job: {url}")


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
    typer.echo(format_job_table(jobs))


@app.command()
def export(
    ctx: typer.Context,
    format: str = typer.Option(
        "json", "--format", "-f", help="Export format: json or csv"
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
    query: str = typer.Option(None, "--query", "-q", help="Filter by search query"),
) -> None:
    """Export jobs to JSON or CSV format."""
    app_ctx: AppContext = ctx.obj
    format = format.lower()

    if format not in ("json", "csv"):
        error(f"Unsupported format: {format}. Use 'json' or 'csv'.")
        raise typer.Exit(1)

    with Session(app_ctx.engine) as session:
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
            "job_posting",
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


@app.command()
def info(ctx: typer.Context) -> None:
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
