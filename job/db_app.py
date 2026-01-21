import json
import typer
from rich.console import Console
from sqlmodel import Session, select, func

from job.core import AppContext, JobAd, JobFitAssessment
from job.utils import error

console = Console()

# Create sub-app for db commands
app = typer.Typer()


@app.command()
def path(ctx: typer.Context) -> None:
    """
    Show the path to the job database.

    Examples:
        job db path
    """
    app_ctx: AppContext = ctx.obj
    db_path = app_ctx.config.db_path

    console.print(f"{db_path}")


@app.command()
def stats(ctx: typer.Context) -> None:
    """
    Show database statistics as JSON.

    Returns counts of jobs and assessments in the database.

    Examples:
        job db stats
    """
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        # Count jobs
        njobs = session.exec(select(func.count(JobAd.id))).one()

        # Count assessments
        nassessments = session.exec(select(func.count(JobFitAssessment.id))).one()

        # Output as JSON
        stats_data = {
            "njobs": njobs,
            "nassessments": nassessments,
        }

        console.print(json.dumps(stats_data))


@app.command(name="del")
def delete(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
) -> None:
    """
    Delete the job database.

    WARNING: This permanently deletes all jobs and assessments.
    Requires confirmation unless --force is used.

    Examples:
        job db del
        job db del --force
    """
    app_ctx: AppContext = ctx.obj
    db_path = app_ctx.config.db_path

    if not db_path.exists():
        error(f"Database not found at: {db_path}")
        raise typer.Exit(1)

    # Confirm deletion unless force flag is set
    if not force:
        console.print(
            f"[yellow]⚠️  WARNING:[/yellow] This will permanently delete: {db_path}"
        )

        with Session(app_ctx.engine) as session:
            njobs = session.exec(select(func.count(JobAd.id))).one()
            nassessments = session.exec(select(func.count(JobFitAssessment.id))).one()

        console.print(
            f"[dim]Database contains {njobs} job(s) and {nassessments} assessment(s)[/dim]"
        )

        confirm = typer.confirm("Are you sure you want to delete the database?")
        if not confirm:
            console.print("[dim]Cancelled[/dim]")
            raise typer.Exit(0)

    # Delete the database file
    try:
        db_path.unlink()
        console.print(f"[green]✓[/green] Deleted database: {db_path}")
    except Exception as e:
        error(f"Failed to delete database: {e}")
        raise typer.Exit(1)
