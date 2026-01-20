# main.py
from pathlib import Path
from typing import Annotated

import typer

from dotenv import load_dotenv
from rich.console import Console

from job.__version__ import __version__ as job_version
from job.core import AppContext, Config

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
    config = Config.from_env(verbose=verbose)
    ctx.obj = AppContext(config=config)


# Import and register sub-apps
from job.search import app as search_app  # noqa: E402
from job.add import app as add_app  # noqa: E402
from job.commands import app as commands_app  # noqa: E402
from job.fit import app as fit_app  # noqa: E402

# Merge all sub-apps at root level for flat command structure
app.add_typer(search_app)
app.add_typer(add_app)
app.add_typer(commands_app)

# Register fit as a command group (not flat, to support subcommands)
app.add_typer(fit_app, name="fit", help="Job fit assessment commands")
app.add_typer(
    fit_app, name="f", help="Job fit assessment commands (alias)", hidden=True
)
