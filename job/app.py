import typer
from functools import cache
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlmodel import Session, desc, select
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry, UnexpectedModelBehavior
from pydantic import ValidationError

from job.core import AppContext, JobAd, JobAppDraft, JobAppDraftBase
from job.utils import error

console = Console()

# Create sub-app for app commands
app = typer.Typer(help="Job application document generation commands")


@cache
def load_prompt(prompt_name: str) -> str:
    """Load prompt from markdown file.

    Args:
        prompt_name: Name of the prompt file (without .md extension)

    Returns:
        Content of the prompt file

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    prompt_path = Path(__file__).parent / "prompts" / f"{prompt_name}.md"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    return prompt_path.read_text(encoding="utf-8")


@cache
def create_app_agent(model: str) -> Agent[None, JobAppDraftBase]:
    """Create and cache an application writer agent for the given model.

    Args:
        model: Model name (e.g., 'gemini-2.5-flash', 'claude-sonnet-4.5')

    Returns:
        Configured PydanticAI agent
    """
    system_prompt = load_prompt("application-writer")

    return Agent(
        model=model,
        output_type=JobAppDraftBase,
        system_prompt=system_prompt,
    )


def read_source_file(path: str) -> dict:
    """Read a TOML/YAML source file and extract the content.

    Args:
        path: Path to the source file

    Returns:
        Dictionary with the parsed content

    Raises:
        typer.Exit: If file cannot be read or parsed
    """
    import tomllib

    import yaml

    file_path = Path(path).expanduser()

    if not file_path.exists():
        error(f"Source file not found: {file_path}")
        raise typer.Exit(1)

    try:
        if path.endswith(".toml"):
            with open(file_path, "rb") as f:
                data = tomllib.load(f)
        else:
            content = file_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)

        return data
    except Exception as e:
        error(f"Failed to parse {file_path}: {e}")
        raise typer.Exit(1)


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
    no_cv: bool = typer.Option(False, "--no-cv", help="Skip CV generation"),
    no_letter: bool = typer.Option(
        False, "--no-letter", help="Skip cover letter generation"
    ),
    model: str = typer.Option(None, "--model", "-m", help="AI model to use"),
    cv_source: str = typer.Option(None, "--cv-source", help="CV source file path"),
    letter_source: str = typer.Option(
        None,
        "--letter-source",
        help="Letter source file path",
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

    gen_cv = not no_cv
    gen_letter = not no_letter

    if not gen_cv and not gen_letter:
        error("Must generate at least one document")
        raise typer.Exit(1)

    # Get job from database
    with Session(app_ctx.engine) as session:
        job = session.get(JobAd, job_id)
        if not job:
            error(f"No job found with ID: {job_id}")
            raise typer.Exit(1)

        # Determine model (CLI > app-specific config > global config)
        final_model = app_ctx.config.get_model(
            model or getattr(app_ctx.config.app, "model", None)
        )

        # Determine source paths
        final_cv_source = cv_source or getattr(
            app_ctx.config.app.write.cv, "source", None
        )
        final_letter_source = letter_source or getattr(
            app_ctx.config.app.write.letter, "source", None
        )

        # Read source files
        cv_data = None
        letter_data = None

        if gen_cv:
            if not final_cv_source:
                error("Must provide --cv or set [job.app.write.cv] field in job.toml")
                raise typer.Exit(1)

            with console.status("[bold dim]Reading CV source file...[/bold dim]"):
                cv_data = read_source_file(final_cv_source)
                console.print(f"[dim]Loaded CV from {final_cv_source}[/dim]")

        if gen_letter:
            if not final_letter_source:
                error(
                    "Must provide --letter or set [job.app.write.letter] field in job.toml"
                )
                raise typer.Exit(1)

            with console.status(
                "[bold dim]Reading cover letter source file...[/bold dim]"
            ):
                letter_data = read_source_file(final_letter_source)
                console.print(f"[dim]Loaded letter from {final_letter_source}[/dim]")

        # Create agent
        agent = create_app_agent(final_model)

        # Build prompt
        prompt_parts = [
            "JOB POSTING:",
            f"URL: {job.job_posting_url}",
            f"Title: {job.title}",
            f"Company: {job.company}",
            f"Location: {job.location}",
            f"Department: {job.department}",
            f"Deadline: {job.deadline}",
            "",
            "Full Job Description:",
            f"{job.full_ad}",
            "",
        ]

        if cv_data:
            import json

            prompt_parts.extend(
                [
                    "CURRENT CV DATA:",
                    json.dumps(cv_data, indent=2),
                    "",
                ]
            )

        if letter_data:
            import json

            prompt_parts.extend(
                [
                    "CURRENT COVER LETTER DATA:",
                    json.dumps(letter_data, indent=2),
                    "",
                ]
            )

        prompt_parts.append(
            "Generate tailored application documents for this job posting."
        )
        prompt = "\n".join(prompt_parts)

        # Run agent
        with console.status(
            f"[bold dim]Generating application with {final_model}...[/bold dim]"
        ):
            try:
                result = agent.run_sync(prompt)
                draft_data = result.output
            except ValidationError as e:
                error(f"AI returned invalid data: {e}")
                raise typer.Exit(1)
            except UnexpectedModelBehavior as e:
                error(f"AI model behaved unexpectedly: {e}")
                raise typer.Exit(1)
            except ModelRetry as e:
                error(f"AI model failed after retries: {e}")
                raise typer.Exit(1)
            except Exception as e:
                error(f"Failed to generate application: {e}")
                raise typer.Exit(1)

        # Store draft
        draft = JobAppDraft(
            job_id=job.id,
            model_name=final_model,
            cv_content=draft_data.cv_content if gen_cv else None,
            letter_content=draft_data.letter_content if gen_letter else None,
            source_cv_path=final_cv_source if gen_cv else None,
            source_letter_path=final_letter_source if gen_letter else None,
            notes=draft_data.notes,
        )

        session.add(draft)
        session.commit()
        session.refresh(draft)

        # Display success
        console.print()
        console.print(
            f"[green]✓[/green] Generated draft {draft.id} for job {job_id}: {job.title}"
        )
        if draft.cv_content:
            console.print(f"  [dim]• CV tailored ({len(draft.cv_content)} chars)[/dim]")
        if draft.letter_content:
            console.print(
                f"  [dim]• Cover letter tailored ({len(draft.letter_content)} chars)[/dim]"
            )
        if draft.notes:
            console.print(f"  [dim]• Notes: {draft.notes[:100]}...[/dim]")
        console.print()
        console.print(f"[dim]View with: job app view {job_id} -i {draft.id}[/dim]")


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
