import typer
from rich.console import Console
from sqlmodel import Session

from job.core import AppContext, JobAd
from job.utils import error

console = Console()

# Create sub-app for update commands
app = typer.Typer(no_args_is_help=True, help="Update job data")


def get_job_by_id(session: Session, job_id: int) -> JobAd:
    """Get job from database by ID.

    Args:
        session: Database session
        job_id: Job ID

    Returns:
        JobAd instance

    Raises:
        typer.Exit: If job not found
    """
    job = session.get(JobAd, job_id)
    if not job:
        error(f"No job found with ID: {job_id}")
        raise typer.Exit(1)
    return job


def get_updatable_fields() -> list[str]:
    """Get list of fields that can be updated."""
    return [
        "job_posting_url",
        "title",
        "company",
        "location",
        "deadline",
        "department",
        "hiring_manager",
        "full_ad",
        "github_repo",
        "github_issue_number",
        "github_issue_url",
    ]


@app.command(name="u", hidden=True)
@app.command(name="upt")
def update(
    ctx: typer.Context,
    job_id: int = typer.Argument(..., help="Job ID to update"),
    field: str = typer.Argument(..., help="Field to update"),
    value: str = typer.Argument(..., help="New value for the field"),
) -> None:
    """
    Update a specific field of a job ad. (Alias: u)

    Updates the specified field of the job with the given ID to the new value.

    Available fields: job_posting_url, title, company, location, deadline,
    department, hiring_manager, full_ad, github_repo, github_issue_number, github_issue_url

    Examples:
        job upt 1 title "Senior Python Developer"
        job upt 1 company "Google"
        job u 2 location "San Francisco, CA"
    """
    app_ctx: AppContext = ctx.obj

    # Validate field name
    valid_fields = get_updatable_fields()
    if field not in valid_fields:
        error(f"Invalid field '{field}'. Valid fields: {', '.join(valid_fields)}")
        raise typer.Exit(1)

    # Handle special cases for field types
    if field == "github_issue_number":
        try:
            # Convert string to int for github_issue_number
            processed_value = int(value) if value.lower() != "null" else None
        except ValueError:
            error(f"Field '{field}' must be a valid integer")
            raise typer.Exit(1)
    else:
        # For all other fields, allow None by using "null" string
        processed_value = None if value.lower() == "null" else value

    with Session(app_ctx.engine) as session:
        # Get the job
        job = get_job_by_id(session, job_id)

        # Store old value for display
        old_value = getattr(job, field)

        # Update the field
        setattr(job, field, processed_value)
        session.add(job)
        session.commit()
        session.refresh(job)

        # Display the change
        console.print(f"[green]✓[/green] Updated job {job_id}:")
        console.print(f"  [dim]Field:[/dim] {field}")
        console.print(f"  [dim]Old:[/dim] {old_value}")
        console.print(f"  [dim]New:[/dim] {processed_value}")
