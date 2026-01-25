import typer
from rich.console import Console
from sqlmodel import Session, select, func

from job.core import AppContext, JobAd, JobFitAssessment, JobAppDraft
from job.utils import error

console = Console()

# Create sub-app for db commands
app = typer.Typer(no_args_is_help=True, help="Job database management commands")


@app.command()
def path(ctx: typer.Context) -> None:
    """
    Show the path to the job database.

    Examples:
        job db path
    """
    app_ctx: AppContext = ctx.obj
    db_path = app_ctx.config.get_db_path()

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
        n_jobs = session.exec(select(func.count(JobAd.id))).one()

        # Count assessments
        n_fits = session.exec(select(func.count(JobFitAssessment.id))).one()

        # Count app drafts
        n_apps = session.exec(select(func.count(JobAppDraft.id))).one()

        # Output each stat on a new line
        console.print(f"n_jobs: {n_jobs}")
        console.print(f"n_fits: {n_fits}")
        console.print(f"n_apps: {n_apps}")


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
    db_path = app_ctx.config.get_db_path()

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


@app.command()
def migrate(ctx: typer.Context) -> None:
    """
    Migrate database schema to latest version.

    Adds new columns to existing tables if they don't exist.
    Safe to run multiple times (idempotent).

    Examples:
        job db migrate
    """
    app_ctx: AppContext = ctx.obj

    with console.status("[bold dim]Migrating database schema...[/bold dim]"):
        # Get raw connection to execute ALTER TABLE statements
        with app_ctx.engine.connect() as conn:
            # Check if github_repo column exists
            result = conn.exec_driver_sql(
                "SELECT COUNT(*) FROM pragma_table_info('jobad') WHERE name='github_repo'"
            )
            has_github_fields = result.scalar() > 0

            if not has_github_fields:
                # Add GitHub metadata columns
                conn.exec_driver_sql("ALTER TABLE jobad ADD COLUMN github_repo VARCHAR")
                conn.exec_driver_sql(
                    "ALTER TABLE jobad ADD COLUMN github_issue_number INTEGER"
                )
                conn.exec_driver_sql(
                    "ALTER TABLE jobad ADD COLUMN github_issue_url VARCHAR"
                )
                conn.exec_driver_sql("ALTER TABLE jobad ADD COLUMN posted_at DATETIME")
                conn.commit()

                console.print(
                    "[green]✓[/green] Added GitHub metadata columns to jobad table"
                )
            else:
                console.print("[dim]Database schema is already up to date[/dim]")

    console.print("[green]✓[/green] Migration complete")
