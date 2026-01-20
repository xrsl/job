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
from job.utils import error, validate_url

console = Console()

# Create sub-app for fit commands
# Set invoke_without_command=True to allow both direct invocation and subcommands
app = typer.Typer(invoke_without_command=True)


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

    Supports both individual files and directories (scanned recursively).
    Directories will read common text formats: .md, .txt, .toml, .yaml, .yml, .json

    Args:
        context_paths: List of file or directory paths to read

    Returns:
        Tuple of (combined_content, valid_paths)

    Raises:
        typer.Exit: If any path cannot be read
    """
    # Common text file extensions to read from directories
    TEXT_EXTENSIONS = {".md", ".txt", ".toml", ".yaml", ".yml", ".json"}

    combined_content = []
    valid_paths = []

    for path_str in context_paths:
        path = Path(path_str).expanduser()

        if not path.exists():
            error(f"Context path not found: {path}")
            raise typer.Exit(1)

        # Collect files to read
        files_to_read = []

        if path.is_file():
            files_to_read.append(path)
        elif path.is_dir():
            # Recursively find all text files
            for ext in TEXT_EXTENSIONS:
                files_to_read.extend(path.rglob(f"*{ext}"))

            if not files_to_read:
                error(f"No text files found in directory: {path}")
                raise typer.Exit(1)
        else:
            error(f"Context path is neither a file nor directory: {path}")
            raise typer.Exit(1)

        # Read all collected files
        for file_path in files_to_read:
            try:
                content = file_path.read_text(encoding="utf-8")
                # Use relative path from original input for better readability
                if path.is_dir():
                    display_name = str(file_path.relative_to(path.parent))
                else:
                    display_name = file_path.name
                combined_content.append(f"=== {display_name} ===\n{content}\n")
                valid_paths.append(str(file_path.absolute()))
            except Exception as e:
                error(f"Failed to read {file_path}: {e}")
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


@app.callback(invoke_without_command=True)
def fit(
    ctx: typer.Context,
    url: str = typer.Option(None, "--url", "-u", help="Job posting URL"),
    job_id: int = typer.Option(None, "--id", "-i", help="Job ID from database"),
    context: list[str] = typer.Option(
        None,
        "--context",
        "-c",
        help="Context file or directory paths (CV, experience, etc.). Directories are scanned recursively for text files.",
    ),
    model: str = typer.Option(None, "--model", "-m", help="AI model to use"),
) -> None:
    """
    Assess job fit against candidate context.

    Analyzes how well a job matches your background based on CV and other context files.
    Requires either --url or --id to specify the job, and at least one --context file or directory.

    Context paths can be:
    - Individual files (any format, read as text)
    - Directories (recursively scanned for .md, .txt, .toml, .yaml, .yml, .json files)
    - Mix of both

    Examples:
        job fit --url example.com --context cv.toml --context EXPERIENCE.md
        job fit --id 2 --context reference/ -m claude-sonnet-4.5
        job fit view --id 2  (view saved assessments)
    """
    # If a subcommand was invoked, don't run the assessment logic
    if ctx.invoked_subcommand is not None:
        return

    app_ctx: AppContext = ctx.obj

    # Validate arguments (only if running assessment, not subcommand)
    if not context:
        error("Must provide at least one --context file")
        raise typer.Exit(1)
    if not url and job_id is None:
        error("Must provide either --url or --id")
        raise typer.Exit(1)

    if url and job_id is not None:
        error("Cannot provide both --url and --id")
        raise typer.Exit(1)

    if not context:
        error("Must provide at least one --context file")
        raise typer.Exit(1)

    # Override model if specified
    if model:
        from dataclasses import replace

        app_ctx.config = replace(app_ctx.config, model=model)

    # Read context files
    with console.status("[bold dim]Reading context files...[/bold dim]"):
        context_content, context_paths = read_context_files(context)

    console.print(f"[dim]Loaded {len(context_paths)} context file(s)[/dim]")

    # Get job from database
    job: JobAd | None = None

    with Session(app_ctx.engine) as session:
        if job_id is not None:
            # Look up by ID
            job = session.get(JobAd, job_id)
            if not job:
                error(f"No job found with ID: {job_id}")
                raise typer.Exit(1)
        else:
            # Look up by URL
            final_url = validate_url(url)
            job = session.exec(
                select(JobAd).where(JobAd.job_posting_url == final_url)
            ).first()

            if not job:
                error(f"Job not found in database: {final_url}")
                console.print("[dim]Run 'job add <url>' first to add the job[/dim]")
                raise typer.Exit(1)

        # Run fit assessment
        agent = create_fit_agent(app_ctx.config.model)

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
            f"[bold dim]Analyzing fit with {app_ctx.config.model}...[/bold dim]"
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
            model_name=app_ctx.config.model,
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
    job_id: int = typer.Option(
        None, "--id", "-i", help="Job ID to view assessments for"
    ),
    assessment_id: int = typer.Option(
        None, "--assessment-id", "-a", help="Specific assessment ID to view directly"
    ),
) -> None:
    """
    View stored fit assessments. (Alias: v)

    View either a specific assessment by ID, or all assessments for a job.
    Requires either --id or --assessment-id.

    Examples:
        job fit view -a 5        (view assessment 5)
        job fit view -i 1        (list all assessments for job 1)
        job fit v -a 3           (using alias)
    """
    app_ctx: AppContext = ctx.obj

    # Validate arguments
    if job_id is None and assessment_id is None:
        error("Must provide either --id (job ID) or --assessment-id")
        raise typer.Exit(1)

    with Session(app_ctx.engine) as session:
        # If assessment_id is provided, view that specific one
        if assessment_id is not None:
            assessment = session.get(JobFitAssessment, assessment_id)
            if not assessment:
                error(f"No assessment found with ID: {assessment_id}")
                raise typer.Exit(1)

            # Get the job
            job = session.get(JobAd, assessment.job_id)
            if not job:
                error(f"Job not found for assessment {assessment_id}")
                raise typer.Exit(1)

            assert assessment.id is not None  # ID exists for loaded record
            display_fit_assessment(job, assessment, assessment.id)
            return

        # Otherwise, list assessments for the job
        # Get the job
        job = session.get(JobAd, job_id)
        if not job:
            error(f"No job found with ID: {job_id}")
            raise typer.Exit(1)

        # Get all assessments for this job
        assessments = session.exec(
            select(JobFitAssessment)
            .where(JobFitAssessment.job_id == job_id)
            .order_by(JobFitAssessment.created_at.desc())
        ).all()

        if not assessments:
            error(f"No fit assessments found for job ID {job_id}")
            console.print(
                f"[dim]Run 'job fit --id {job_id} --context <files>' to create an assessment[/dim]"
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
    assessment_id: int = typer.Option(
        None, "--assessment-id", "-a", help="Delete specific assessment by ID"
    ),
    job_id: int = typer.Option(
        None, "--job-id", "-i", help="Delete all assessments for a job"
    ),
) -> None:
    """
    Delete fit assessments from database.

    Delete either a specific assessment by ID, or all assessments for a job.
    Requires either --assessment-id or --job-id.

    Examples:
        job fit rm -a 5           (delete assessment 5)
        job fit rm -i 1           (delete all assessments for job 1)
    """
    app_ctx: AppContext = ctx.obj

    # Validate arguments
    if assessment_id is None and job_id is None:
        error("Must provide either --assessment-id or --job-id")
        raise typer.Exit(1)

    if assessment_id is not None and job_id is not None:
        error("Cannot provide both --assessment-id and --job-id")
        raise typer.Exit(1)

    with Session(app_ctx.engine) as session:
        if assessment_id is not None:
            # Delete specific assessment
            assessment = session.get(JobFitAssessment, assessment_id)
            if not assessment:
                error(f"No assessment found with ID: {assessment_id}")
                raise typer.Exit(1)

            session.delete(assessment)
            session.commit()
            console.print(f"[green]✓[/green] Deleted assessment {assessment_id}")

        else:
            # Delete all assessments for a job
            # First verify job exists
            job = session.get(JobAd, job_id)
            if not job:
                error(f"No job found with ID: {job_id}")
                raise typer.Exit(1)

            # Get all assessments
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


@app.command(name="p", hidden=True)
@app.command()
def post(
    ctx: typer.Context,
    assessment_id: int = typer.Option(
        ..., "--assessment-id", "-a", help="Assessment ID to post"
    ),
    issue: int = typer.Option(..., "--issue", help="GitHub issue number"),
    repo: str = typer.Option(..., "--repo", help="GitHub repository (owner/repo)"),
) -> None:
    """
    Post fit assessment as GitHub issue comment. (Alias: p)

    Formats the assessment as markdown and posts it as a comment to a GitHub issue
    using the gh CLI tool.

    Examples:
        job fit post -a 5 --issue 45 --repo xrsl/bla
        job fit p -a 3 --issue 12 --repo owner/repo
    """
    app_ctx: AppContext = ctx.obj

    with Session(app_ctx.engine) as session:
        # Get the assessment
        assessment = session.get(JobFitAssessment, assessment_id)
        if not assessment:
            error(f"No assessment found with ID: {assessment_id}")
            raise typer.Exit(1)

        # Get the job
        job = session.get(JobAd, assessment.job_id)
        if not job:
            error(f"Job not found for assessment {assessment_id}")
            raise typer.Exit(1)

        # Format assessment as markdown
        context_files = json.loads(assessment.context_file_paths)
        context_display = ", ".join([Path(p).name for p in context_files])

        # Parse strengths and gaps
        strengths = json.loads(assessment.strengths)
        gaps = json.loads(assessment.gaps)

        # Build markdown comment
        markdown = f"""## Job Fit Assessment

**Job:** [{job.title}]({job.job_posting_url})
**Company:** {job.company}
**Location:** {job.location}

---

### Overall Fit: {assessment.overall_fit_score}/100

{assessment.fit_summary}

---

### ✅ Strengths

{chr(10).join([f"- {s}" for s in strengths])}

---

### ⚠️ Gaps

{chr(10).join([f"- {g}" for g in gaps])}

---

### 💡 Recommendations

{assessment.recommendations}

---

### 🔍 Key Insights

{assessment.key_insights}

---

<details>
<summary>Assessment Details</summary>

**Model:** {assessment.model_name}
**Created:** {assessment.created_at.strftime("%Y-%m-%d %H:%M:%S")}
**Context:** {context_display}
**Assessment ID:** {assessment_id}

</details>
"""

        # Write to temp file for gh CLI
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(markdown)
            temp_path = f.name

        try:
            # Post using gh CLI
            import subprocess

            console.print(
                f"[dim]Posting assessment {assessment_id} to {repo}#{issue}...[/dim]"
            )

            result = subprocess.run(
                [
                    "gh",
                    "issue",
                    "comment",
                    str(issue),
                    "--repo",
                    repo,
                    "--body-file",
                    temp_path,
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                error(f"Failed to post comment: {result.stderr}")
                raise typer.Exit(1)

            console.print(f"[green]✓[/green] Posted assessment to {repo}#{issue}")

            # Try to get the comment URL from output
            if result.stdout.strip():
                console.print(f"[dim]{result.stdout.strip()}[/dim]")

        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
