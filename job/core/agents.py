"""Shared AI agent creation utilities."""

from functools import cache
from pathlib import Path
from typing import cast

from pydantic_ai import Agent

from job.core.models import JobAdBase, JobAppDraftBase, JobFitAssessmentBase


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
    prompt_path = Path(__file__).parent.parent / "prompts" / f"{prompt_name}.md"

    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

    return prompt_path.read_text(encoding="utf-8")


@cache
def create_agent(model: str, system_prompt: str) -> Agent[None, JobAdBase]:
    """Create and cache an AI agent for extracting job ads."""
    return cast(
        Agent[None, JobAdBase],
        Agent(
            model=model,
            output_type=JobAdBase,
            system_prompt=system_prompt,
        ),
    )


@cache
def create_app_agent(model: str) -> Agent[None, JobAppDraftBase]:
    """Create and cache an application writer agent for the given model."""
    system_prompt = load_prompt("application-writer")
    return cast(
        Agent[None, JobAppDraftBase],
        Agent(
            model=model,
            output_type=JobAppDraftBase,
            system_prompt=system_prompt,
        ),
    )


@cache
def create_fit_agent(model: str) -> Agent[None, JobFitAssessmentBase]:
    """Create and cache a career advisor agent for the given model."""
    system_prompt = load_prompt("career-advisor")
    return cast(
        Agent[None, JobFitAssessmentBase],
        Agent(
            model=model,
            output_type=JobFitAssessmentBase,
            system_prompt=system_prompt,
        ),
    )
