"""GitHub integration commands."""

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console
from sqlmodel import Session

from job.core import AppContext, JobAd, JobFitAssessment
from job.utils import error

console = Console()

# Create sub-app for GitHub commands
app = typer.Typer(no_args_is_help=True, help="GitHub integration commands")


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


@app.command(name="i", hidden=True, no_args_is_help=True)
@app.command(no_args_is_help=True)
def issue(
    ctx: typer.Context,
    from_job: int = typer.Option(..., "--from-job", "-f", help="Job ID from database"),
    repo: str = typer.Option(
        None,
        "--repo",
        "-r",
        help="GitHub repository (owner/repo, from config if not specified)",
    ),
    force: bool = typer.Option(False, "--force", help="Create even if already posted"),
) -> None:
    """
    Create GitHub issue from job posting. (Alias: i)

    Creates a GitHub issue with the job details. Prevents duplicate creation
    by tracking which jobs have already been posted (unless --force is used).

    Examples:
        job gh issue --from-job 2 --repo xrsl/cv
        job gh i -f 2 --repo owner/repo
        job gh i -f 2  # uses repo from job.toml
    """
    app_ctx: AppContext = ctx.obj

    # Use repo from config if not provided via CLI
    final_repo = repo or app_ctx.config.gh.repo
    if not final_repo:
        error("Repository not specified")
        console.print("[dim]Provide --repo or set [job.gh] repo in job.toml[/dim]")
        raise typer.Exit(1)

    with Session(app_ctx.engine) as session:
        # Get the job
        job = get_job_by_id(session, from_job)

        # Check if already posted
        if job.github_issue_number is not None and not force:
            error(f"Job already posted to {job.github_repo}#{job.github_issue_number}")
            console.print(f"[dim]Issue URL: {job.github_issue_url}[/dim]")
            console.print("[dim]Use --force to create a new issue anyway[/dim]")
            raise typer.Exit(1)

        # Build issue body in markdown
        issue_body = f"""**Company:** {job.company}
**Location:** {job.location}
**Department:** {job.department or "N/A"}
**Deadline:** {job.deadline or "N/A"}
**Hiring Manager:** {job.hiring_manager or "N/A"}

**Job Posting:** {job.job_posting_url}

---

## Full Job Description

{job.full_ad}
"""

        # Write to temp file for gh CLI
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(issue_body)
            temp_path = f.name

        try:
            # Create issue using gh CLI
            console.print(f"[dim]Creating issue in {final_repo}...[/dim]")

            result = subprocess.run(
                [
                    "gh",
                    "issue",
                    "create",
                    "--repo",
                    final_repo,
                    "--title",
                    f"{job.title} at {job.company}",
                    "--body-file",
                    temp_path,
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                error(f"Failed to create issue: {result.stderr}")
                raise typer.Exit(1)

            # Parse issue URL from output
            issue_url = result.stdout.strip()

            # Extract issue number from URL (format: https://github.com/owner/repo/issues/123)
            try:
                issue_number = int(issue_url.split("/")[-1])
            except (ValueError, IndexError):
                error(f"Could not parse issue number from: {issue_url}")
                raise typer.Exit(1)

            # Update job with GitHub metadata
            job.github_repo = final_repo
            job.github_issue_number = issue_number
            job.github_issue_url = issue_url
            job.posted_at = datetime.now(timezone.utc)

            session.add(job)
            session.commit()

            console.print(f"[green]✓[/green] Created issue: {issue_url}")
            console.print(f"[dim]Job ID {job.id} → {final_repo}#{issue_number}[/dim]")

        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)


@app.command(name="c", hidden=True, no_args_is_help=True)
@app.command(no_args_is_help=True)
def comment(
    ctx: typer.Context,
    assessment_id: int = typer.Option(
        ..., "--assessment", "-a", help="Assessment ID to post"
    ),
    repo: str = typer.Option(
        None,
        "--repo",
        "-r",
        help="GitHub repository (owner/repo, auto-detected if job was posted)",
    ),
    issue: int = typer.Option(
        None, "--issue", help="GitHub issue number (auto-detected if job was posted)"
    ),
) -> None:
    """
    Post fit assessment as GitHub issue comment. (Alias: c)

    Formats the assessment as markdown and posts it as a comment to a GitHub issue.
    If the job was previously posted via 'job gh issue', repo and issue number
    are auto-detected from the database.

    Examples:
        job gh comment -a 5 --repo xrsl/cv --issue 45
        job gh c -a 5  # auto-detect repo/issue from job metadata
        job gh c -a 3 --issue 12  # auto-detect repo only
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

        # Auto-detect repo and issue from job metadata if not provided
        final_repo = repo or job.github_repo
        final_issue = issue or job.github_issue_number

        if not final_repo:
            error("Repository not specified and job has no GitHub metadata")
            console.print(
                "[dim]Provide --repo or create issue first with 'job gh issue'[/dim]"
            )
            raise typer.Exit(1)

        if not final_issue:
            error("Issue number not specified and job has no GitHub metadata")
            console.print(
                "[dim]Provide --issue or create issue first with 'job gh issue'[/dim]"
            )
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
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(markdown)
            temp_path = f.name

        try:
            # Post using gh CLI
            console.print(
                f"[dim]Posting assessment {assessment_id} to {final_repo}#{final_issue}...[/dim]"
            )

            result = subprocess.run(
                [
                    "gh",
                    "issue",
                    "comment",
                    str(final_issue),
                    "--repo",
                    final_repo,
                    "--body-file",
                    temp_path,
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                error(f"Failed to post comment: {result.stderr}")
                raise typer.Exit(1)

            console.print(
                f"[green]✓[/green] Posted assessment to {final_repo}#{final_issue}"
            )

            # Try to get the comment URL from output
            if result.stdout.strip():
                console.print(f"[dim]{result.stdout.strip()}[/dim]")

        finally:
            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)
