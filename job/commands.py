# commands.py
import typer
from sqlmodel import Session, select, desc

from job.main import app, engine, JobAd


@app.command(name="list")
def list_jobs():
    """List all stored job ads."""
    with Session(engine) as session:
        jobs = session.exec(select(JobAd).order_by(desc(JobAd.id))).all()

    if not jobs:
        typer.echo("No jobs found.")
        return

    # Calculate column widths
    url_w = max(len("URL"), max(len(j.job_posting or "") for j in jobs))
    title_w = max(len("TITLE"), max(len(j.title or "") for j in jobs))
    company_w = max(len("COMPANY"), max(len(j.company or "") for j in jobs))
    location_w = max(len("LOCATION"), max(len(j.location or "") for j in jobs))

    # Header
    typer.echo(f"{"TITLE":<{title_w}}  {"COMPANY":<{company_w}}  {"LOCATION":<{location_w}}  {"URL":<{url_w}}")

    # Rows
    for job in jobs:
        typer.echo(f"{(job.title or ""):<{title_w}}  {(job.company or ""):<{company_w}}  {(job.location or ""):<{location_w}}  {(job.job_posting or ""):<{url_w}}")


@app.command()
def show(url: str = typer.Argument(..., help="Job posting URL")):
    """Show a single job ad by URL."""
    with Session(engine) as session:
        job = session.exec(
            select(JobAd).where(JobAd.job_posting == url)
        ).first()

    if not job:
        typer.echo(f"No job found with url={url}", err=True)
        raise typer.Exit(1)

    typer.echo(job.model_dump_json(indent=2))


@app.command()
def rm(url: str = typer.Argument(..., help="Job posting URL")):
    """Delete a job ad by URL."""
    with Session(engine) as session:
        job = session.exec(
            select(JobAd).where(JobAd.job_posting == url)
        ).first()
        if not job:
            typer.echo(f"No job found with url={url}", err=True)
            raise typer.Exit(1)

        session.delete(job)
        session.commit()

    typer.echo(f"Deleted job: {url}")


@app.command()
def search(
    query: str = typer.Argument(..., help="Search keywords"),
):
    """Search jobs by keyword (title, company, department, location, body)."""
    q = f"%{query.lower()}%"

    with Session(engine) as session:
        jobs = session.exec(
            select(JobAd).where(
                (JobAd.title.ilike(q)) |
                (JobAd.company.ilike(q)) |
                (JobAd.department.ilike(q)) |
                (JobAd.location.ilike(q)) |
                (JobAd.job_ad.ilike(q))
            ).order_by(desc(JobAd.id))
        ).all()

    if not jobs:
        typer.echo("No matching jobs found.")
        return

    # Calculate column widths
    url_w = max(len("URL"), max(len(j.job_posting or "") for j in jobs))
    title_w = max(len("TITLE"), max(len(j.title or "") for j in jobs))
    company_w = max(len("COMPANY"), max(len(j.company or "") for j in jobs))
    location_w = max(len("LOCATION"), max(len(j.location or "") for j in jobs))

    # Header
    typer.echo(f"{"TITLE":<{title_w}}  {"COMPANY":<{company_w}}  {"LOCATION":<{location_w}}  {"URL":<{url_w}}")

    # Rows
    for job in jobs:
        typer.echo(f"{(job.title or ""):<{title_w}}  {(job.company or ""):<{company_w}}  {(job.location or ""):<{location_w}}  {(job.job_posting or ""):<{url_w}}")

