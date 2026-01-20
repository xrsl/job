# main.py
from pathlib import Path
from typing import Annotated

import typer

from dotenv import load_dotenv
from rich.console import Console

from job.__version__ import __version__ as job_version
from job.core import AppContext, Config

console = Console()

# Load environment variables from multiple locations (first found wins)
_env_locations = [
    Path.home() / ".config" / "job" / ".env",  # XDG-style config
    Path.home() / ".job.env",  # Home directory dotfile
    Path.cwd() / ".env",  # Current directory (for development)
]

for _env_path in _env_locations:
    if _env_path.exists():
        load_dotenv(_env_path)
        break
else:
    # Fallback: try default behavior (CWD)
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
    config = Config.from_env(verbose=verbose)
    ctx.obj = AppContext(config=config)


# Import and register sub-apps
from job.search import app as search_app  # noqa: E402
from job.add import app as add_app  # noqa: E402
from job.commands import app as commands_app  # noqa: E402

# Merge all sub-apps at root level for flat command structure
app.add_typer(search_app)
app.add_typer(add_app)
app.add_typer(commands_app)
