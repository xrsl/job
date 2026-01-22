# commands.py
import json
import sys
from typing import Sequence

import typer
from rich.console import Console
from rich.table import Table
from sqlmodel import Session, col, desc, select

from job.core import AppContext, JobAd
from job.utils import error, validate_url

console = Console()

# Create sub-app for job management commands
app = typer.Typer()


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
@app.command(name="l", hidden=True)
@app.command(name="ls", hidden=True)
@app.command(name="list")
def list_jobs(ctx: typer.Context) -> None:
    """List all stored job ads. (Alias: l)"""
    app_ctx: AppContext = ctx.obj
    with Session(app_ctx.engine) as session:
        jobs = session.exec(select(JobAd).order_by(desc(JobAd.id))).all()

    if not jobs:
        typer.echo("No jobs found.")
        return

    format_job_table(jobs)


@app.command(name="v", hidden=True)
@app.command(name="show", hidden=True)
@app.command(name="view")
def view_job(
    ctx: typer.Context,
    identifier: str = typer.Argument(..., help="Job ID or URL"),
    json_output: bool = typer.Option(False, "--json", help="Output as raw JSON"),
) -> None:
    """View a single job ad by ID or URL. (Alias: v)"""
    from rich.panel import Panel

    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        job = get_job_by_id_or_url(session, identifier)

        if not job:
            # If get_job_by_id_or_url returned None (and didn't exit), it means not found
            error(f"No job found with ID or URL matching: {identifier}")
            raise typer.Exit(1)

        if json_output:
            typer.echo(job.model_dump_json(indent=2))
        else:
            # Rich formatted output
            console.print()
            console.print(
                Panel(
                    f"[bold]{job.title or 'N/A'}[/bold]\n"
                    f"[dim]{job.company or 'N/A'} • {job.location or 'N/A'}[/dim]\n"
                    f"[link={job.job_posting_url}]{job.job_posting_url}[/link]",
                    title=f"Job Ad #{job.id}",
                    border_style="blue",
                )
            )

            # Job Details
            console.print()
            details = []
            if job.department:
                details.append(f"[bold]Department:[/bold] {job.department}")
            if job.deadline:
                details.append(f"[bold]Deadline:[/bold] {job.deadline}")
            if job.hiring_manager:
                details.append(f"[bold]Hiring Manager:[/bold] {job.hiring_manager}")
            if job.posted_at:
                details.append(
                    f"[bold]Posted:[/bold] {job.posted_at.strftime('%Y-%m-%d')}"
                )
            if job.github_issue_url:
                details.append(
                    f"[bold]GitHub Issue:[/bold] [link={job.github_issue_url}]{job.github_issue_url}[/link]"
                )

            if details:
                console.print(
                    Panel(
                        "\n".join(details),
                        title="Details",
                        border_style="cyan",
                    )
                )

            # Full Job Description
            if job.full_ad:
                console.print()
                # Replace literal \n with actual newlines for display
                formatted_ad = job.full_ad.replace("\\n", "\n")
                console.print(
                    Panel(
                        formatted_ad,
                        title="Job Description",
                        border_style="green",
                    )
                )

            console.print()


@app.command(name="d", hidden=True)
@app.command(name="rm", hidden=True)
@app.command(name="del")
def delete_job(
    ctx: typer.Context,
    identifier: str = typer.Argument(..., help="Job ID or URL"),
) -> None:
    """Delete a job ad by ID or URL. (Alias: d)"""
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


@app.command(name="q", hidden=True)
@app.command(name="find", hidden=True)
@app.command(name="query")
def query_jobs(
    ctx: typer.Context,
    query: str = typer.Argument(..., help="Search keywords"),
) -> None:
    """Query jobs in local database by keyword (title, company, department, location, body). (Alias: q)"""
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
                | (col(JobAd.full_ad).ilike(q))
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
    identifier: str = typer.Argument(
        None, help="Job ID or URL to export (exports all if omitted)"
    ),
    output: str = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
    query: str = typer.Option(None, "--query", "-q", help="Filter by search query"),
) -> None:
    """Export jobs to JSON format. (Alias: e)

    Export a specific job by ID or URL, or all jobs (optionally filtered by query).
    Examples:
        job e 1           # Export job with ID 1
        job e             # Export all jobs
        job e -q "python" # Export jobs matching query
    """
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        jobs = []

        # If identifier provided, fetch that specific job
        if identifier:
            job = get_job_by_id_or_url(session, identifier)
            if job:
                jobs.append(job)
            else:
                error(f"No job found with ID or URL: {identifier}")
                raise typer.Exit(1)
        else:
            # No identifier: fetch all (optionally filtered by query)
            stmt = select(JobAd).order_by(desc(JobAd.id))

            if query:
                q = f"%{query.lower()}%"
                stmt = stmt.where(
                    (col(JobAd.title).ilike(q))
                    | (col(JobAd.company).ilike(q))
                    | (col(JobAd.department).ilike(q))
                    | (col(JobAd.location).ilike(q))
                    | (col(JobAd.full_ad).ilike(q))
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
