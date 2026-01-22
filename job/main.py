# main.py
from pathlib import Path
from typing import Annotated

import typer

from dotenv import load_dotenv
from rich.console import Console

from job.__version__ import __version__ as job_version
from job.config import settings
from job.core import AppContext
from job.search import app as search_app
from job.add import app as add_app
from job.commands import app as commands_app
from job.fit import app as fit_app
from job.app import app as app_app
from job.db import app as db_app
from job.gh import app as gh_app

console = Console()

# Load environment variables
# 1. Load system/global config first
global_env_locations = [
    Path.home() / ".config" / "job" / ".env",
    Path.home() / ".job.env",
]
for _env_path in global_env_locations:
    if _env_path.exists():
        load_dotenv(_env_path)
        break

# 2. Load local config (overrides global)
local_env = Path.cwd() / ".env"
if local_env.exists():
    load_dotenv(local_env, override=True)
else:
    # Fallback if no specific files found above, try default behavior
    if not any(p.exists() for p in global_env_locations):
        load_dotenv()


# Main CLI application instance
app = typer.Typer(
    invoke_without_command=True,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def version_option_callback(value: bool):
    if value:
        print(job_version)
        raise typer.Exit()


version_option = typer.Option(
    "--version",
    "-V",
    callback=version_option_callback,
    is_eager=True,
    help="Show version.",
)


@app.callback(epilog="Made with :purple_heart: in [bold blue]Copenhagen[/bold blue].")
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose/debug output"
    ),
    version: Annotated[bool | None, version_option] = None,
) -> None:
    """Job CLI - manage job postings."""
    if verbose:
        settings.verbose = True
    ctx.obj = AppContext(config=settings)


@app.command(hidden=True)
def lm(
    filter_str: str = typer.Argument("", help="Filter models by provider or name"),
) -> None:
    """List available AI models (hidden utility command)."""
    from collections import defaultdict
    from typing import get_args

    try:
        from pydantic_ai.models import KnownModelName
    except ImportError:
        console.print(
            "[red]Error: Could not import pydantic_ai.models.KnownModelName[/red]"
        )
        console.print("[dim]Ensure pydantic-ai is installed.[/dim]")
        raise typer.Exit(1)

    # Extract models from KnownModelName
    try:
        if hasattr(KnownModelName, "__value__"):
            models = get_args(KnownModelName.__value__)
        else:
            models = get_args(KnownModelName)
    except Exception as e:
        console.print(f"[red]Error extracting models: {e}[/red]")
        raise typer.Exit(1)

    if not models:
        console.print("[yellow]No models found in KnownModelName.[/yellow]")
        return

    # Group by provider
    by_provider = defaultdict(list)
    for m in models:
        if ":" in m:
            provider, _ = m.split(":", 1)
            by_provider[provider].append(m)
        else:
            by_provider["other"].append(m)

    console.print(f"[bold]Found {len(models)} known models in pydantic_ai.[/bold]\n")

    filter_lower = filter_str.lower()

    for provider in sorted(by_provider.keys()):
        # Filter by provider or model name
        if filter_lower:
            matching_models = [
                m
                for m in by_provider[provider]
                if filter_lower in m.lower() or filter_lower in provider.lower()
            ]
            if not matching_models:
                continue
        else:
            matching_models = by_provider[provider]

        console.print(f"[bold cyan]--- {provider.upper()} ---[/bold cyan]")
        for m in sorted(matching_models):
            console.print(f"  {m}")
        console.print()

    console.print("[dim]Usage example:[/dim]")
    console.print("  [dim]job add https://example.com/job -s -m openai:gpt-4o[/dim]")
    console.print(
        "  [dim]job add https://example.com/job -s -m anthropic:claude-3-5-sonnet-latest[/dim]"
    )


# Merge all sub-apps at root level for flat command structure
app.add_typer(add_app)
app.add_typer(search_app)
app.add_typer(commands_app)

# commands that has subcommands
app.add_typer(fit_app, name="fit")
app.add_typer(fit_app, name="f", hidden=True)
app.add_typer(app_app, name="app")
app.add_typer(db_app, name="db")
app.add_typer(gh_app, name="gh")
