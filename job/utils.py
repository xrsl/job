import json
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar
from urllib.parse import urlparse

import typer
from pydantic import ValidationError
from pydantic_ai.exceptions import ModelRetry, UnexpectedModelBehavior
from rich.console import Console
from sqlmodel import Session

# Date/time format constant
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"

console = Console()

T = TypeVar("T")


def error(message: str) -> None:
    """Print an error message to stderr."""
    typer.echo(f"Error: {message}", err=True)


def validate_url(url: str) -> str:
    """Validate and normalize a URL. Raises typer.Exit on invalid URL."""
    url = url.strip()

    # Add scheme if missing
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            error(f"Invalid URL: missing domain in '{url}'")
            raise typer.Exit(1)
        if parsed.scheme not in ("http", "https"):
            error(f"Invalid URL scheme: '{parsed.scheme}' (must be http or https)")
            raise typer.Exit(1)
        # Check for valid domain (must have a dot for TLD, unless localhost)
        if "." not in parsed.netloc and "localhost" not in parsed.netloc.lower():
            error(f"Invalid domain: '{parsed.netloc}' (missing TLD)")
            raise typer.Exit(1)
        return url
    except ValueError as e:
        error(f"Invalid URL format: {e}")
        raise typer.Exit(1)


def read_context_files(
    context_paths: list[str], return_paths: bool = False
) -> str | tuple[str, list[str]]:
    """Read multiple context files and combine their contents.

    Args:
        context_paths: List of file paths to read
        return_paths: If True, also return list of valid paths

    Returns:
        Combined content string, or tuple of (content, valid_paths) if return_paths=True

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
            console.print(
                f"[dim]Skipped binary file: {path.name}[/dim]", style="yellow"
            )
            continue
        except Exception as e:
            error(f"Failed to read {path}: {e}")
            raise typer.Exit(1)

    result = "\n".join(combined_content)
    if return_paths:
        return result, valid_paths
    return result


def parse_json_or_list(value: list | str) -> list:
    """Parse a value that might be a list or JSON string.

    Args:
        value: Either a list or a JSON-encoded string

    Returns:
        The parsed list
    """
    if isinstance(value, list):
        return value
    return json.loads(value)


def get_score_style(score: int) -> tuple[str, str]:
    """Get display style and label for a fit score.

    Args:
        score: Fit score (0-100)

    Returns:
        Tuple of (style, label) for rich formatting
    """
    if score >= 80:
        return "bold green", "EXCELLENT MATCH"
    elif score >= 60:
        return "bold yellow", "GOOD MATCH"
    elif score >= 40:
        return "bold orange", "MODERATE MATCH"
    else:
        return "bold red", "POOR MATCH"


def get_score_color(score: int) -> str:
    """Get color for a fit score (for table display).

    Args:
        score: Fit score (0-100)

    Returns:
        Color name for rich formatting
    """
    if score >= 80:
        return "green"
    elif score >= 60:
        return "yellow"
    elif score >= 40:
        return "orange1"
    else:
        return "red"


@contextmanager
def handle_ai_errors(operation: str):
    """Context manager for handling AI agent errors.

    Args:
        operation: Description of the operation (e.g., "extract job info")

    Raises:
        typer.Exit: On any AI-related error
    """
    try:
        yield
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
        error(f"Failed to {operation}: {e}")
        raise typer.Exit(1)


def get_or_exit(session: Session, model_class: type[T], id: int, name: str) -> T:
    """Get an entity by ID or exit with error.

    Args:
        session: Database session
        model_class: SQLModel class to query
        id: Entity ID
        name: Human-readable name for error messages (e.g., "job", "assessment")

    Returns:
        The entity instance

    Raises:
        typer.Exit: If entity not found
    """
    entity = session.get(model_class, id)
    if not entity:
        error(f"No {name} found with ID: {id}")
        raise typer.Exit(1)
    return entity
