# commands.py
import csv
import json
import sys
from io import StringIO
from typing import Sequence

import typer
from sqlmodel import Session, desc, select

from job.main import JobAd, app, error, get_engine, log, validate_url


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
def list_jobs() -> None:
    """List all stored job ads."""
    engine = get_engine()
    with Session(engine) as session:
        jobs = session.exec(select(JobAd).order_by(desc(JobAd.id))).all()

    if not jobs:
        typer.echo("No jobs found.")
        return

    typer.echo(format_job_table(jobs))


@app.command()
def show(url: str = typer.Argument(..., help="Job posting URL")) -> None:
    """Show a single job ad by URL."""
    url = validate_url(url)
    engine = get_engine()

    with Session(engine) as session:
        job = session.exec(select(JobAd).where(JobAd.job_posting == url)).first()

    if not job:
        error(f"No job found with url={url}")
        raise typer.Exit(1)

    typer.echo(job.model_dump_json(indent=2))


@app.command()
def rm(url: str = typer.Argument(..., help="Job posting URL")) -> None:
    """Delete a job ad by URL."""
    url = validate_url(url)
    engine = get_engine()

    with Session(engine) as session:
        job = session.exec(select(JobAd).where(JobAd.job_posting == url)).first()
        if not job:
            error(f"No job found with url={url}")
            raise typer.Exit(1)

        session.delete(job)
        session.commit()

    typer.echo(f"Deleted job: {url}")


@app.command()
def find(
    query: str = typer.Argument(..., help="Search keywords"),
) -> None:
    """Find jobs in local database by keyword (title, company, department, location, body)."""
    q = f"%{query.lower()}%"
    log(f"Searching for: {query}")
    engine = get_engine()

    with Session(engine) as session:
        jobs = session.exec(
            select(JobAd)
            .where(
                (JobAd.title.ilike(q))
                | (JobAd.company.ilike(q))
                | (JobAd.department.ilike(q))
                | (JobAd.location.ilike(q))
                | (JobAd.job_ad.ilike(q))
            )
            .order_by(desc(JobAd.id))
        ).all()

    if not jobs:
        typer.echo("No matching jobs found.")
        return

    log(f"Found {len(jobs)} matching jobs")
    typer.echo(format_job_table(jobs))


@app.command()
def export(
    format: str = typer.Option(
        "json", "--format", "-f", help="Export format: json or csv"
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
    query: str = typer.Option(None, "--query", "-q", help="Filter by search query"),
) -> None:
    """Export jobs to JSON or CSV format."""
    engine = get_engine()
    format = format.lower()

    if format not in ("json", "csv"):
        error(f"Unsupported format: {format}. Use 'json' or 'csv'.")
        raise typer.Exit(1)

    with Session(engine) as session:
        stmt = select(JobAd).order_by(desc(JobAd.id))

        if query:
            q = f"%{query.lower()}%"
            stmt = stmt.where(
                (JobAd.title.ilike(q))
                | (JobAd.company.ilike(q))
                | (JobAd.department.ilike(q))
                | (JobAd.location.ilike(q))
                | (JobAd.job_ad.ilike(q))
            )

        jobs = session.exec(stmt).all()

    if not jobs:
        typer.echo("No jobs to export.")
        return

    log(f"Exporting {len(jobs)} jobs as {format}")

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
def info() -> None:
    """Show database location and statistics."""
    from job.main import get_db_path

    db_path = get_db_path()
    engine = get_engine()

    with Session(engine) as session:
        count = len(session.exec(select(JobAd)).all())

    typer.echo(f"Database: {db_path}")
    typer.echo(f"Total jobs: {count}")

    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        typer.echo(f"Database size: {size_kb:.1f} KB")
