import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlmodel import Session, desc, select

from job.core import AppContext, JobAd, JobAppDraft
from job.utils import error

console = Console()

# Create sub-app for app commands
app = typer.Typer(help="Job application document generation commands")


# TODO: Implement read_source_file and write_source_file functions
# when AI agent integration is added


@app.command(name="ls")
def list_drafts(
    ctx: typer.Context,
    job_id: int = typer.Argument(..., help="Job ID to list drafts for"),
) -> None:
    """
    List all application drafts for a job.

    Shows all AI-generated application documents stored for this job.

    Examples:
        job app ls 42
    """
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        # Verify job exists
        job = session.get(JobAd, job_id)
        if not job:
            error(f"No job found with ID: {job_id}")
            raise typer.Exit(1)

        # Get all drafts for this job
        drafts = session.exec(
            select(JobAppDraft)
            .where(JobAppDraft.job_id == job_id)
            .order_by(desc(JobAppDraft.created_at))
        ).all()

        if not drafts:
            console.print(
                f"[yellow]No application drafts found for job {job_id}[/yellow]"
            )
            console.print(f"[dim]Run 'job app write {job_id}' to generate one[/dim]")
            return

        # Display header
        console.print()
        console.print(
            Panel(
                f"[bold]{job.title}[/bold]\n[dim]{job.company} • {job.location}[/dim]",
                title="Job Posting",
                border_style="blue",
            )
        )
        console.print()

        # Display table of drafts
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("ID", style="dim", width=6)
        table.add_column("Date", width=20)
        table.add_column("Model", width=25)
        table.add_column("Has CV", width=8)
        table.add_column("Has Letter", width=10)

        for draft in drafts:
            has_cv = "[green]✓[/green]" if draft.cv_content else "[dim]−[/dim]"
            has_letter = "[green]✓[/green]" if draft.letter_content else "[dim]−[/dim]"

            table.add_row(
                str(draft.id),
                draft.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                draft.model_name,
                has_cv,
                has_letter,
            )

        console.print(table)
        console.print()


@app.command(name="w", hidden=True)
@app.command()
def write(
    ctx: typer.Context,
    job_id: int = typer.Argument(..., help="Job ID to generate application for"),
    cv: bool = typer.Option(True, "--cv/--no-cv", help="Generate CV"),
    letter: bool = typer.Option(
        True, "--letter/--no-letter", help="Generate cover letter"
    ),
    model: str = typer.Option(
        None, "--model", "-m", help="AI model to use (from config if not specified)"
    ),
    cv_source: str = typer.Option(
        None, "--cv-source", help="CV source file path (from config if not specified)"
    ),
    letter_source: str = typer.Option(
        None,
        "--letter-source",
        help="Letter source file path (from config if not specified)",
    ),
) -> None:
    """
    Generate tailored application documents with AI. (Alias: w)

    Creates AI-generated CV and/or cover letter tailored to the job posting.
    Requires job_id as positional argument.

    Examples:
        job app write 42
        job app w 42 --no-letter
        job app write 42 -m gpt-4o --cv-source src/cv.toml
    """
    app_ctx: AppContext = ctx.obj

    if not cv and not letter:
        error("Must generate at least one document (--cv or --letter)")
        raise typer.Exit(1)

    # Get job from database
    with Session(app_ctx.engine) as session:
        job = session.get(JobAd, job_id)
        if not job:
            error(f"No job found with ID: {job_id}")
            raise typer.Exit(1)

        # Determine model
        final_model = app_ctx.config.get_model(
            model or getattr(app_ctx.config, "app", None) and app_ctx.config.app.model
        )

        # TODO: Read source files, call AI agent, store results
        # For now, create a placeholder draft
        console.print(
            "[yellow]TODO: Implement AI agent for document generation[/yellow]"
        )
        console.print(f"[dim]Model: {final_model}[/dim]")
        console.print(f"[dim]Generate CV: {cv}[/dim]")
        console.print(f"[dim]Generate Letter: {letter}[/dim]")

        # Create draft record (placeholder)
        draft = JobAppDraft(
            job_id=job.id,
            model_name=final_model,
            cv_content="# Placeholder CV content" if cv else None,
            letter_content="# Placeholder letter content" if letter else None,
            source_cv_path=cv_source,
            source_letter_path=letter_source,
        )

        session.add(draft)
        session.commit()
        session.refresh(draft)

        console.print(f"[green]✓[/green] Created draft {draft.id} for job {job_id}")


@app.command(name="v", hidden=True)
@app.command()
def view(
    ctx: typer.Context,
    job_id: int = typer.Argument(..., help="Job ID to view draft for"),
    draft_id: int = typer.Option(..., "-i", help="Draft ID to view"),
) -> None:
    """
    View a specific application draft. (Alias: v)

    Display the generated CV and/or cover letter content.
    Requires both job_id and -i draft_id.

    Examples:
        job app view 42 -i 1
        job app v 42 -i 1
    """
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        # Verify job exists
        job = session.get(JobAd, job_id)
        if not job:
            error(f"No job found with ID: {job_id}")
            raise typer.Exit(1)

        # Get draft
        draft = session.get(JobAppDraft, draft_id)
        if not draft:
            error(f"No draft found with ID: {draft_id}")
            raise typer.Exit(1)

        # Verify draft belongs to job
        if draft.job_id != job_id:
            error(f"Draft {draft_id} does not belong to job {job_id}")
            raise typer.Exit(1)

        # Display header
        console.print()
        console.print(
            Panel(
                f"[bold]{job.title}[/bold]\n[dim]{job.company} • {job.location}[/dim]",
                title="Job Posting",
                border_style="blue",
            )
        )

        # Display metadata
        console.print()
        console.print(
            Panel(
                f"[bold]Model:[/bold] {draft.model_name}\n"
                f"[bold]Created:[/bold] {draft.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"[bold]Draft ID:[/bold] {draft.id}",
                title="Draft Metadata",
                border_style="dim",
            )
        )

        # Display CV content
        if draft.cv_content:
            console.print()
            console.print(
                Panel(
                    draft.cv_content,
                    title="[bold green]CV Content[/bold green]",
                    border_style="green",
                )
            )

        # Display letter content
        if draft.letter_content:
            console.print()
            console.print(
                Panel(
                    draft.letter_content,
                    title="[bold blue]Cover Letter Content[/bold blue]",
                    border_style="blue",
                )
            )

        console.print()


@app.command()
def rm(
    ctx: typer.Context,
    job_id: int = typer.Argument(..., help="Job ID to delete drafts for"),
    draft_id: int = typer.Option(
        None,
        "-i",
        help="Specific draft ID to delete (deletes all if not provided)",
    ),
) -> None:
    """
    Delete application drafts from database.

    Delete either all drafts for a job, or a specific draft with -i flag.
    Requires job_id as positional argument.

    Examples:
        job app rm 42           (delete all drafts for job 42)
        job app rm 42 -i 1      (delete only draft 1 for job 42)
    """
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        # Verify job exists
        job = session.get(JobAd, job_id)
        if not job:
            error(f"No job found with ID: {job_id}")
            raise typer.Exit(1)

        if draft_id is not None:
            # Delete specific draft
            draft = session.get(JobAppDraft, draft_id)
            if not draft:
                error(f"No draft found with ID: {draft_id}")
                raise typer.Exit(1)

            # Verify draft belongs to job
            if draft.job_id != job_id:
                error(f"Draft {draft_id} does not belong to job {job_id}")
                raise typer.Exit(1)

            session.delete(draft)
            session.commit()
            console.print(f"[green]✓[/green] Deleted draft {draft_id} for job {job_id}")
        else:
            # Delete all drafts for job
            drafts = session.exec(
                select(JobAppDraft).where(JobAppDraft.job_id == job_id)
            ).all()

            if not drafts:
                error(f"No drafts found for job ID {job_id}")
                raise typer.Exit(1)

            count = len(drafts)
            for draft in drafts:
                session.delete(draft)
            session.commit()

            console.print(
                f"[green]✓[/green] Deleted {count} draft{'s' if count != 1 else ''} for job {job_id}: {job.title}"
            )
