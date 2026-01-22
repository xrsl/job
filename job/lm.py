from collections import defaultdict
from typing import get_args

import typer
from rich.console import Console
from pydantic_ai.models import KnownModelName
# <gateway>/<provider>:<model>

console = Console()
app = typer.Typer(
    invoke_without_command=True, help="List ai models supported by pydantic-ai"
)


@app.callback()
def list_models(
    ctx: typer.Context,
    include: str | None = typer.Argument(
        None, help="Filter models by provider or name"
    ),
    exclude: list[str] = typer.Option(
        None, "--exclude", "-e", help="Exclude models containing this string."
    ),
) -> None:
    """
    List available AI models.
    """

    # KnownModelName is a TypeAliasType in newer versions, so we need to access __value__
    model_type = getattr(KnownModelName, "__value__", KnownModelName)
    models = get_args(model_type)

    # Group by provider
    by_provider = defaultdict(list)
    for m in models:
        if ":" in m:
            provider, _ = m.split(":", 1)
            by_provider[provider].append(m)
        else:
            by_provider["other"].append(m)

    console.print(f"[bold]Found {len(models)} known models in pydantic_ai.[/bold]\n")

    include_lower = include.lower() if include else None
    excludes_lower = [e.lower() for e in exclude] if exclude else []

    for provider_key in sorted(by_provider.keys()):
        # Filter by provider or model name (search term)
        if include_lower:
            candidates = [
                m
                for m in by_provider[provider_key]
                if include_lower in m.lower() or include_lower in provider_key.lower()
            ]
        else:
            candidates = by_provider[provider_key]

        # Apply excludes
        if excludes_lower:
            matching_models = [
                m
                for m in candidates
                if not any(ex in m.lower() for ex in excludes_lower)
            ]
        else:
            matching_models = candidates

        if not matching_models:
            continue

        console.print(f"[bold cyan]--- {provider_key.upper()} ---[/bold cyan]")
        for m in sorted(matching_models):
            console.print(f"  {m}")
        console.print()

    console.print("[dim]Usage example:[/dim]")
    console.print("  [dim]job add https://example.com/job -s -m openai:gpt-4o[/dim]")
    console.print(
        "  [dim]job add https://example.com/job -s -m anthropic:claude-3-5-sonnet-latest[/dim]"
    )
