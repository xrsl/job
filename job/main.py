# main.py
from pathlib import Path
from typing import Annotated

import typer

from dotenv import load_dotenv
from rich.console import Console

from job.__version__ import __version__ as job_version
from job.core import AppContext, Config
from job.cli_app import app

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


# Import commands to register them with the app
from job import add  # noqa: E402, F401
from job import commands  # noqa: E402, F401
from job import search  # noqa: E402, F401

if __name__ == "__main__":
    app()
