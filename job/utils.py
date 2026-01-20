from urllib.parse import urlparse
import typer


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
