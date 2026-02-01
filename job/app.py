import typer
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlmodel import Session, desc, select

from job.core import AppContext, JobAd, JobAppDraft
from job.core.agents import create_app_agent
from job.utils import (
    DATETIME_FORMAT,
    error,
    get_or_exit,
    handle_ai_errors,
    read_context_files,
)

console = Console()

# Create sub-app for app commands
app = typer.Typer(
    no_args_is_help=True,
    help="Write/manage application documents with ai",
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


def _write_source_file(path: str, data: dict, field_name: str) -> None:
    """Write structured data back to TOML/YAML file.

    Args:
        path: Destination file path
        data: Dictionary data to write
        field_name: Root field name (e.g., 'cv', 'letter')

    Similar to cvx build's writeData function.
    """
    import shutil
    import subprocess

    import yaml

    file_path = Path(path).expanduser()

    # Wrap data in field name
    wrapper = {field_name: data}

    # Detect format and marshal
    if path.endswith(".toml"):
        # Python's tomllib doesn't support writing, use tomli_w
        try:
            import tomli_w

            content = tomli_w.dumps(wrapper)
        except ImportError:
            error("tomli_w package required for writing TOML files")
            raise typer.Exit(1)
    else:
        content = yaml.dump(wrapper, default_flow_style=False, sort_keys=False)

    # Write to file
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    # Auto-format TOML with tombi if available
    if path.endswith(".toml") and shutil.which("tombi"):
        subprocess.run(["tombi", "format", str(file_path)], check=False)


def _apply_draft_to_files(
    draft: JobAppDraft, cv_dest: str | None = None, letter_dest: str | None = None
) -> None:
    """Apply draft content to source files.

    Args:
        draft: The draft to apply
        cv_dest: Optional CV destination path (uses draft.source_cv_path if not provided)
        letter_dest: Optional letter destination path (uses draft.source_letter_path if not provided)

    Raises:
        typer.Exit: If application fails
    """
    import json

    # Determine destination paths
    final_cv_dest = cv_dest or draft.source_cv_path
    final_letter_dest = letter_dest or draft.source_letter_path

    # Write CV if present
    if draft.cv_content:
        if not final_cv_dest:
            error("No CV destination path specified and none in draft")
            raise typer.Exit(1)

        try:
            # Try parsing as JSON first (AI should output dict serialized as JSON)
            cv_data = json.loads(draft.cv_content)
            # If data is already wrapped in {"cv": ...}, extract it
            if "cv" in cv_data and len(cv_data) == 1:
                cv_data = cv_data["cv"]
        except json.JSONDecodeError:
            # If JSON parsing fails, try parsing as TOML/YAML content
            try:
                if final_cv_dest.endswith(".toml"):
                    import tomllib

                    cv_data = tomllib.loads(draft.cv_content)
                else:
                    import yaml

                    cv_data = yaml.safe_load(draft.cv_content)
                # Extract the cv field if present
                if "cv" in cv_data and len(cv_data) == 1:
                    cv_data = cv_data["cv"]
            except Exception as e:
                error(f"Failed to parse CV content as JSON, TOML, or YAML: {e}")
                console.print(
                    "[dim]The stored CV content appears to be malformed.[/dim]"
                )
                raise typer.Exit(1)

        try:
            _write_source_file(final_cv_dest, cv_data, "cv")
            console.print(f"[green]✓[/green] CV applied to {final_cv_dest}")
        except Exception as e:
            error(f"Failed to write CV: {e}")
            raise typer.Exit(1)

    # Write letter if present
    if draft.letter_content:
        if not final_letter_dest:
            error("No letter destination path specified and none in draft")
            raise typer.Exit(1)

        try:
            # Try parsing as JSON first (AI should output dict serialized as JSON)
            letter_data = json.loads(draft.letter_content)
            # If data is already wrapped in {"letter": ...}, extract it
            if "letter" in letter_data and len(letter_data) == 1:
                letter_data = letter_data["letter"]
        except json.JSONDecodeError:
            # If JSON parsing fails, try parsing as TOML/YAML content
            try:
                if final_letter_dest.endswith(".toml"):
                    import tomllib

                    letter_data = tomllib.loads(draft.letter_content)
                else:
                    import yaml

                    letter_data = yaml.safe_load(draft.letter_content)
                # Extract the letter field if present
                if "letter" in letter_data and len(letter_data) == 1:
                    letter_data = letter_data["letter"]
            except Exception as e:
                error(f"Failed to parse letter content as JSON, TOML, or YAML: {e}")
                console.print(
                    "[dim]The stored letter content appears to be malformed.[/dim]"
                )
                raise typer.Exit(1)

        try:
            _write_source_file(final_letter_dest, letter_data, "letter")
            console.print(f"[green]✓[/green] Letter applied to {final_letter_dest}")
        except Exception as e:
            error(f"Failed to write letter: {e}")
            raise typer.Exit(1)

    if not draft.cv_content and not draft.letter_content:
        console.print("[yellow]No content to apply[/yellow]")


@app.command(name="l", hidden=True)
@app.command(name="ls", hidden=True)
@app.command(name="list")
def list_drafts(
    ctx: typer.Context,
    job_id: int = typer.Argument(None, help="Job ID to list drafts for (optional)"),
) -> None:
    """
    List application drafts. (Alias: l)

    List all drafts globally or for a specific job if job_id is provided.

    Examples:
        job app list             (list all drafts)
        job app l                (using alias)
        job app list 42          (list drafts for job 42)
    """
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        # Build query based on job_id
        if job_id is not None:
            # Verify job exists
            job = get_or_exit(session, JobAd, job_id, "job")

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
                console.print(
                    f"[dim]Run 'job app write {job_id}' to generate one[/dim]"
                )
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
        else:
            # Get all drafts across all jobs
            drafts = session.exec(
                select(JobAppDraft).order_by(desc(JobAppDraft.created_at))
            ).all()

            if not drafts:
                console.print("[yellow]No application drafts found[/yellow]")
                console.print(
                    "[dim]Run 'job app write <job_id>' to generate drafts[/dim]"
                )
                return

        # Display table of drafts
        console.print()
        table = Table(show_header=True, header_style="bold cyan")

        if job_id is None:
            table.add_column("Job ID", style="dim", width=8)

        table.add_column("Draft ID", style="dim", width=10)
        table.add_column("Date", width=20)
        table.add_column("Model", width=25)
        table.add_column("Has CV", width=8)
        table.add_column("Has Letter", width=10)

        if job_id is None:
            table.add_column("Job Title", width=30)

        for draft in drafts:
            has_cv = "[green]✓[/green]" if draft.cv_content else "[dim]−[/dim]"
            has_letter = "[green]✓[/green]" if draft.letter_content else "[dim]−[/dim]"

            if job_id is None:
                # Get job info for this draft
                job_for_draft = session.get(JobAd, draft.job_id)
                job_title = job_for_draft.title if job_for_draft else "Unknown"
                if len(job_title) > 27:
                    job_title = job_title[:24] + "..."

                table.add_row(
                    str(draft.job_id),
                    str(draft.id),
                    draft.created_at.strftime(DATETIME_FORMAT),
                    draft.model_name,
                    has_cv,
                    has_letter,
                    job_title,
                )
            else:
                table.add_row(
                    str(draft.id),
                    draft.created_at.strftime(DATETIME_FORMAT),
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
    no_apply: bool = typer.Option(
        False, "--no-apply", help="Don't apply changes to source files"
    ),
    model: str = typer.Option(None, "--model", "-m", help="AI model to use"),
    cv: str = typer.Option(None, "--cv", help="CV source file path"),
    letter: str = typer.Option(None, "--letter", help="Letter source file path"),
    extra: list[str] = typer.Option(
        None,
        "--extra",
        "-e",
        help="Extra context file paths (from config if not specified)",
    ),
) -> None:
    """
    Generate tailored application documents with AI. (Alias: w)

    Creates AI-generated CV and/or cover letter tailored to the job posting.
    By default, applies changes to source files. Use --no-apply to only store in database.
    Requires job_id as positional argument.

    Examples:
        job app write 42
        job app w 42 --no-letter
        job app write 42 -m gpt-4o --cv cv.toml --letter letter.toml
        job app w 42 --extra persona.md --extra experience.md
        job app w 42 --no-apply   (store in DB but don't modify files)
    """
    app_ctx: AppContext = ctx.obj

    gen_cv = not no_cv
    gen_letter = not no_letter

    if not gen_cv and not gen_letter:
        error("Must generate at least one document")
        raise typer.Exit(1)

    # Get job from database
    with Session(app_ctx.engine) as session:
        job = get_or_exit(session, JobAd, job_id, "job")

        # Determine model (CLI > app-specific config > global config)
        final_model = app_ctx.config.get_model(
            model or getattr(app_ctx.config.app, "model", None)
        )

        # Determine source paths
        final_cv = cv or getattr(app_ctx.config.app, "cv", None)
        final_letter = letter or getattr(app_ctx.config.app, "letter", None)

        # Collect extra context files (CLI + config)
        final_extra = []
        if extra:
            final_extra.extend(extra)
        if hasattr(app_ctx.config.app, "extra") and app_ctx.config.app.extra:
            final_extra.extend(app_ctx.config.app.extra)

        # Read source files
        cv_data = None
        letter_data = None
        extra_context = None

        if gen_cv:
            if not final_cv:
                error("Must provide --cv or set job.app.cv in job.toml")
                raise typer.Exit(1)

            with console.status("[bold dim]Reading CV source file...[/bold dim]"):
                cv_data = read_source_file(final_cv)
                console.print(f"[dim]Loaded CV from {final_cv}[/dim]")

        if gen_letter:
            if not final_letter:
                error("Must provide --letter or set job.app.letter in job.toml")
                raise typer.Exit(1)

            with console.status(
                "[bold dim]Reading cover letter source file...[/bold dim]"
            ):
                letter_data = read_source_file(final_letter)
                console.print(f"[dim]Loaded letter from {final_letter}[/dim]")

        # Read extra context files if provided
        if final_extra:
            with console.status("[bold dim]Reading extra context files...[/bold dim]"):
                extra_context = read_context_files(final_extra)
                console.print(
                    f"[dim]Loaded {len(final_extra)} extra context file(s)[/dim]"
                )

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

        if extra_context:
            prompt_parts.extend(
                [
                    "ADDITIONAL CONTEXT:",
                    extra_context,
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
            with handle_ai_errors("generate application"):
                result = agent.run_sync(prompt)
                draft_data = result.output

        # Store draft
        draft = JobAppDraft(
            job_id=job.id,
            model_name=final_model,
            cv_content=draft_data.cv_content if gen_cv else None,
            letter_content=draft_data.letter_content if gen_letter else None,
            source_cv_path=final_cv if gen_cv else None,
            source_letter_path=final_letter if gen_letter else None,
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

        # Apply changes to source files unless --no-apply is set
        if not no_apply:
            console.print()
            _apply_draft_to_files(draft)
            console.print()

        console.print(f"[dim]View with: job app view {job_id} -i {draft.id}[/dim]")


@app.command(name="v", hidden=True)
@app.command()
def view(
    ctx: typer.Context,
    id_arg: int = typer.Argument(
        ..., help="Draft ID, or Job ID if -i is specified", metavar="ID"
    ),
    draft_id_opt: int | None = typer.Option(
        None, "-i", "--id", help="Draft ID (if first arg is Job ID)"
    ),
) -> None:
    """
    View a specific application draft. (Alias: v)

    Display the generated CV and/or cover letter content.
    Can be used in two ways:
    1. job app view <draft_id>
    2. job app view <job_id> -i <draft_id> (legacy/explicit)

    Examples:
        job app view 2           (view draft 2)
        job app v 2              (view draft 2 using alias)
        job app v 42 -i 1        (view draft 1 for job 42)
    """
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        # Determine draft_id and optional job_verification_id
        target_draft_id = None
        job_verification_id = None

        if draft_id_opt is not None:
            # Case 2: job_id and draft_id provided
            job_verification_id = id_arg
            target_draft_id = draft_id_opt
        else:
            # Case 1: Only draft_id provided
            target_draft_id = id_arg

        # Get draft
        draft = get_or_exit(session, JobAppDraft, target_draft_id, "draft")

        # If job ID was provided, verify it matches
        if job_verification_id is not None and draft.job_id != job_verification_id:
            error(
                f"Draft {target_draft_id} does not belong to job {job_verification_id}"
            )
            raise typer.Exit(1)

        # Get job info from the draft
        job = get_or_exit(session, JobAd, draft.job_id, "job")

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
                f"[bold]Created:[/bold] {draft.created_at.strftime(DATETIME_FORMAT)}\n"
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


@app.command(name="a", hidden=True)
@app.command()
def apply(
    ctx: typer.Context,
    job_id: int = typer.Argument(..., help="Job ID"),
    draft_id: int = typer.Option(..., "-i", "--id", help="Draft ID to apply"),
    cv_dest: str = typer.Option(None, "--cv-dest", help="CV destination file path"),
    letter_dest: str = typer.Option(
        None, "--letter-dest", help="Letter destination file path"
    ),
) -> None:
    """
    Apply AI-generated content back to source files. (Alias: a)

    Writes the CV/letter content from a draft back to the source TOML/YAML files.
    Note: By default, 'job app write' now applies changes automatically.
    Use this command to re-apply a draft or apply to different destination files.

    Examples:
        job app apply 42 -i 1
        job app a 42 -i 1 --cv-dest src/tailored-cv.toml
    """
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        # Get the draft
        draft = session.get(JobAppDraft, draft_id)
        if not draft or draft.job_id != job_id:
            error(f"No draft found with ID {draft_id} for job {job_id}")
            raise typer.Exit(1)

        _apply_draft_to_files(draft, cv_dest, letter_dest)


@app.command(name="d", hidden=True)
@app.command(name="rm", hidden=True)
@app.command(name="del")
def delete_drafts(
    ctx: typer.Context,
    job_id: int = typer.Argument(..., help="Job ID to delete drafts for"),
    draft_id: int = typer.Option(
        None,
        "-i",
        help="Specific draft ID to delete (deletes all if not provided)",
    ),
) -> None:
    """
    Delete application drafts from database. (Alias: d)

    Delete either all drafts for a job, or a specific draft with -i flag.
    Requires job_id as positional argument.

    Examples:
        job app del 42           (delete all drafts for job 42)
        job app del 42 -i 1      (delete only draft 1 for job 42)
    """
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        # Verify job exists
        job = get_or_exit(session, JobAd, job_id, "job")

        if draft_id is not None:
            # Delete specific draft
            draft = get_or_exit(session, JobAppDraft, draft_id, "draft")

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
