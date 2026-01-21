import json
import typer
from functools import cache
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from sqlmodel import Session, select
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry, UnexpectedModelBehavior
from pydantic import ValidationError

from job.core import AppContext, JobAd, JobFitAssessment, JobFitAssessmentBase
from job.utils import error

console = Console()

# Create sub-app for fit commands
app = typer.Typer(help="Job fit assessment commands (Alias: f)")


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


def read_context_files(context_paths: list[str]) -> tuple[str, list[str]]:
    """Read multiple context files and combine their contents.

    Supports individual files only (any file type including PDFs).

    Args:
        context_paths: List of file paths to read

    Returns:
        Tuple of (combined_content, valid_paths)

    Raises:
        typer.Exit: If any path cannot be read
    """
    combined_content = []
    valid_paths = []

    for path_str in context_paths:
        path = Path(path_str).expanduser()

        if not path.exists():
            error(f"File not found: {path}")
            raise typer.Exit(1)

        if not path.is_file():
            error(f"Path is not a file: {path}")
            raise typer.Exit(1)

        try:
            content = path.read_text(encoding="utf-8")
            combined_content.append(f"=== {path.name} ===\n{content}\n")
            valid_paths.append(str(path.absolute()))
        except UnicodeDecodeError:
            # For binary files (like PDFs), skip with a note
            console.print(
                f"[dim]Skipped binary file: {path.name}[/dim]", style="yellow"
            )
            continue
        except Exception as e:
            error(f"Failed to read {path}: {e}")
            raise typer.Exit(1)

    return "\n".join(combined_content), valid_paths


@cache
def create_fit_agent(model: str) -> Agent[None, JobFitAssessmentBase]:
    """Create and cache a career advisor agent for the given model.

    Args:
        model: Model name (e.g., 'gemini-2.5-flash', 'claude-sonnet-4.5')

    Returns:
        Configured PydanticAI agent
    """
    system_prompt = load_prompt("career-advisor")

    return Agent(
        model=model,
        output_type=JobFitAssessmentBase,
        system_prompt=system_prompt,
    )


def display_fit_assessment(
    job: JobAd, assessment: JobFitAssessmentBase | JobFitAssessment, assessment_id: int
) -> None:
    """Display fit assessment in a nice format."""

    # Header
    console.print()
    console.print(
        Panel(
            f"[bold]{job.title}[/bold]\n"
            f"[dim]{job.company} • {job.location}[/dim]\n"
            f"[link={job.job_posting_url}]{job.job_posting_url}[/link]",
            title="Job Posting",
            border_style="blue",
        )
    )

    # Show metadata if this is a stored assessment
    if isinstance(assessment, JobFitAssessment):
        console.print()
        context_files = json.loads(assessment.context_file_paths)
        context_display = "\n".join([f"  • {Path(p).name}" for p in context_files])
        console.print(
            Panel(
                f"[bold]Model:[/bold] {assessment.model_name}\n"
                f"[bold]Created:[/bold] {assessment.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"[bold]Context Files:[/bold]\n{context_display}",
                title="Assessment Metadata",
                border_style="dim",
            )
        )

    # Fit Score
    score = assessment.overall_fit_score
    if score >= 80:
        score_style = "bold green"
        score_label = "EXCELLENT MATCH"
    elif score >= 60:
        score_style = "bold yellow"
        score_label = "GOOD MATCH"
    elif score >= 40:
        score_style = "bold orange"
        score_label = "MODERATE MATCH"
    else:
        score_style = "bold red"
        score_label = "POOR MATCH"

    console.print()
    console.print(
        Panel(
            f"[{score_style}]{score}/100 - {score_label}[/{score_style}]\n\n"
            f"{assessment.fit_summary}",
            title="Overall Assessment",
            border_style="cyan",
        )
    )

    # Strengths
    console.print()
    # Handle both list (from agent) and JSON string (from database)
    strengths = (
        assessment.strengths
        if isinstance(assessment.strengths, list)
        else json.loads(assessment.strengths)
    )
    strengths_text = "\n".join([f"• {strength}" for strength in strengths])
    console.print(
        Panel(
            strengths_text,
            title="[bold green]✓ Strengths[/bold green]",
            border_style="green",
        )
    )

    # Gaps
    console.print()
    gaps = (
        assessment.gaps
        if isinstance(assessment.gaps, list)
        else json.loads(assessment.gaps)
    )
    gaps_text = "\n".join([f"• {gap}" for gap in gaps])
    console.print(
        Panel(
            gaps_text,
            title="[bold red]✗ Gaps[/bold red]",
            border_style="red",
        )
    )

    # Recommendations
    console.print()
    console.print(
        Panel(
            assessment.recommendations,
            title="[bold]💡 Recommendations[/bold]",
            border_style="yellow",
        )
    )

    # Key Insights
    console.print()
    console.print(
        Panel(
            assessment.key_insights,
            title="[bold]🔍 Key Insights[/bold]",
            border_style="magenta",
        )
    )

    console.print()
    console.print(f"[dim]Assessment ID: {assessment_id}[/dim]")


@app.command(name="r", hidden=True)
@app.command()
def run(
    ctx: typer.Context,
    job_id: int = typer.Argument(..., help="Job ID from database"),
    cv: str = typer.Option(
        None,
        "--cv",
        help="CV file path (from config if not specified)",
    ),
    extra: list[str] = typer.Option(
        None,
        "--extra",
        "-e",
        help="Extra context file paths (from config if not specified)",
    ),
    model: str = typer.Option(
        None, "--model", "-m", help="AI model to use (from config if not specified)"
    ),
) -> None:
    """
    Assess job fit against candidate context. (Alias: r)

    Analyzes how well a job matches your background based on CV and other context files.
    Requires job_id as positional argument. CV and extra files can be provided via flags
    or from config (job.toml).

    Examples:
        job fit run 42 --cv cv.pdf --extra persona.md --extra experience.md
        job fit r 42 -e reference.md -m claude-sonnet-4.5
        job fit run 42  # uses cv and extra from job.toml
    """
    app_ctx: AppContext = ctx.obj

    # Build final context list: CV + extra files
    final_context = []

    # Add CV (CLI > config)
    final_cv = cv or app_ctx.config.fit.cv
    if not final_cv:
        error("Must provide --cv or set cv in [job.fit] section of job.toml")
        raise typer.Exit(1)
    final_context.append(final_cv)

    # Add extra files (CLI + config)
    if extra:
        final_context.extend(extra)
    if app_ctx.config.fit.extra:
        final_context.extend(app_ctx.config.fit.extra)

    # Determine model (CLI > fit-specific config > global config)
    final_model = app_ctx.config.get_model(model or app_ctx.config.fit.model)

    # Read context files
    with console.status("[bold dim]Reading context files...[/bold dim]"):
        context_content, context_paths = read_context_files(final_context)

    console.print(f"[dim]Loaded {len(context_paths)} context file(s)[/dim]")

    # Get job from database
    with Session(app_ctx.engine) as session:
        job = session.get(JobAd, job_id)
        if not job:
            error(f"No job found with ID: {job_id}")
            raise typer.Exit(1)

        # Run fit assessment
        agent = create_fit_agent(final_model)

        prompt = f"""Assess the job fit for this candidate.

JOB POSTING:
URL: {job.job_posting_url}
Title: {job.title}
Company: {job.company}
Location: {job.location}
Department: {job.department}
Deadline: {job.deadline}

Full Job Description:
{job.full_ad}

CANDIDATE CONTEXT:
{context_content}

Provide a comprehensive fit assessment."""

        with console.status(
            f"[bold dim]Analyzing fit with {final_model}...[/bold dim]"
        ):
            try:
                result = agent.run_sync(prompt)
                assessment = result.output
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
                error(f"Failed to assess fit: {e}")
                raise typer.Exit(1)

        # Store assessment
        fit_record = JobFitAssessment(
            job_id=job.id,
            model_name=final_model,
            context_file_paths=json.dumps(context_paths),
            overall_fit_score=assessment.overall_fit_score,
            fit_summary=assessment.fit_summary,
            strengths=json.dumps(assessment.strengths),
            gaps=json.dumps(assessment.gaps),
            recommendations=assessment.recommendations,
            key_insights=assessment.key_insights,
        )

        session.add(fit_record)
        session.commit()
        session.refresh(fit_record)

        # Display results
        assert fit_record.id is not None  # ID is set after commit
        display_fit_assessment(job, assessment, fit_record.id)


@app.command(name="v", hidden=True)
@app.command()
def view(
    ctx: typer.Context,
    job_id: int = typer.Argument(..., help="Job ID to view assessments for"),
    assessment_id: int = typer.Option(
        None, "-i", help="Specific assessment ID to view directly"
    ),
) -> None:
    """
    View stored fit assessments. (Alias: v)

    View either all assessments for a job, or a specific assessment with -i flag.
    Requires job_id as positional argument.

    Examples:
        job fit view 1           (list all assessments for job 1)
        job fit view 1 -i 5      (view assessment 5 for job 1)
        job fit v 1              (using alias)
    """
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        # Get the job first
        job = session.get(JobAd, job_id)
        if not job:
            error(f"No job found with ID: {job_id}")
            raise typer.Exit(1)

        # If assessment_id is provided, view that specific one for this job
        if assessment_id is not None:
            assessment = session.get(JobFitAssessment, assessment_id)
            if not assessment:
                error(f"No assessment found with ID: {assessment_id}")
                raise typer.Exit(1)

            # Verify the assessment belongs to this job
            if assessment.job_id != job_id:
                error(f"Assessment {assessment_id} does not belong to job {job_id}")
                raise typer.Exit(1)

            assert assessment.id is not None  # ID exists for loaded record
            display_fit_assessment(job, assessment, assessment.id)
            return

        # Otherwise, list assessments for the job

        # Get all assessments for this job
        assessments = session.exec(
            select(JobFitAssessment)
            .where(JobFitAssessment.job_id == job_id)
            .order_by(JobFitAssessment.created_at.desc())
        ).all()

        if not assessments:
            error(f"No fit assessments found for job ID {job_id}")
            console.print(
                f"[dim]Run 'job fit {job_id} --cv <cv_file> --extra <files>' to create an assessment[/dim]"
            )
            raise typer.Exit(1)

        # If only one assessment, display it
        if len(assessments) == 1:
            assessment = assessments[0]
            assert assessment.id is not None  # ID exists for loaded record
            display_fit_assessment(job, assessment, assessment.id)
            return

        # Multiple assessments - let user pick
        console.print(
            f"\n[bold]Found {len(assessments)} assessments for:[/bold] {job.title} at {job.company}\n"
        )

        from rich.table import Table

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("ID", style="dim", width=6)
        table.add_column("Date", width=20)
        table.add_column("Model", width=20)
        table.add_column("Score", width=10)
        table.add_column("Context Files", width=40)

        for assessment in assessments:
            # Parse context files for display
            context_files = json.loads(assessment.context_file_paths)
            context_display = ", ".join([Path(p).name for p in context_files])
            if len(context_display) > 37:
                context_display = context_display[:34] + "..."

            # Color code score
            if assessment.overall_fit_score >= 80:
                score_display = f"[green]{assessment.overall_fit_score}[/green]"
            elif assessment.overall_fit_score >= 60:
                score_display = f"[yellow]{assessment.overall_fit_score}[/yellow]"
            elif assessment.overall_fit_score >= 40:
                score_display = f"[orange1]{assessment.overall_fit_score}[/orange1]"
            else:
                score_display = f"[red]{assessment.overall_fit_score}[/red]"

            table.add_row(
                str(assessment.id),
                assessment.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                assessment.model_name,
                score_display,
                context_display,
            )

        console.print(table)

        # Let user pick which assessment to view
        console.print()
        try:
            choice = typer.prompt(
                "Enter assessment ID to view in detail (or 'q' to quit)",
                type=str,
            )

            if choice.lower() == "q":
                raise typer.Exit(0)

            assessment_id = int(choice)
            selected = next((a for a in assessments if a.id == assessment_id), None)

            if not selected:
                error(f"Invalid assessment ID: {assessment_id}")
                raise typer.Exit(1)

            # Display the selected assessment
            console.print()
            assert selected.id is not None  # ID exists for loaded record
            display_fit_assessment(job, selected, selected.id)

        except ValueError:
            error("Invalid input. Please enter a number or 'q'")
            raise typer.Exit(1)


@app.command()
def rm(
    ctx: typer.Context,
    job_id: int = typer.Argument(..., help="Job ID to delete assessments for"),
    assessment_id: int = typer.Option(
        None,
        "-i",
        help="Specific assessment ID to delete (deletes all if not provided)",
    ),
) -> None:
    """
    Delete fit assessments from database.

    Delete either all assessments for a job, or a specific assessment with -i flag.
    Requires job_id as positional argument.

    Examples:
        job fit rm 1              (delete all assessments for job 1)
        job fit rm 1 -i 2         (delete only assessment 2 for job 1)
    """
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        # First verify job exists
        job = session.get(JobAd, job_id)
        if not job:
            error(f"No job found with ID: {job_id}")
            raise typer.Exit(1)

        if assessment_id is not None:
            # Delete specific assessment for this job
            assessment = session.get(JobFitAssessment, assessment_id)
            if not assessment:
                error(f"No assessment found with ID: {assessment_id}")
                raise typer.Exit(1)

            # Verify the assessment belongs to this job
            if assessment.job_id != job_id:
                error(f"Assessment {assessment_id} does not belong to job {job_id}")
                raise typer.Exit(1)

            session.delete(assessment)
            session.commit()
            console.print(
                f"[green]✓[/green] Deleted assessment {assessment_id} for job {job_id}"
            )

        else:
            # Delete all assessments for the job
            assessments = session.exec(
                select(JobFitAssessment).where(JobFitAssessment.job_id == job_id)
            ).all()

            if not assessments:
                error(f"No assessments found for job ID {job_id}")
                raise typer.Exit(1)

            # Delete all
            count = len(assessments)
            for assessment in assessments:
                session.delete(assessment)
            session.commit()

            console.print(
                f"[green]✓[/green] Deleted {count} assessment{'s' if count != 1 else ''} for job {job_id}: {job.title}"
            )
