# scan.py
"""
Career page scanning functionality.
"""
import re
from dataclasses import dataclass, field
from typing import Iterator

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from job.main import _fetch_with_playwright, _fetch_with_requests, app, error, log
from job.search_config import CareerPage, SearchConfig, load_config

console = Console()

# Minimum content length to consider the page loaded
MIN_CONTENT_LENGTH = 200


@dataclass
class SearchMatch:
    """A keyword match found on a career page."""

    keyword: str
    count: int
    context_snippets: list[str] = field(default_factory=list)


@dataclass
class PageScanResult:
    """Result of scanning a single career page."""

    page: CareerPage
    success: bool
    matches: list[SearchMatch] = field(default_factory=list)
    error_message: str = ""
    content_length: int = 0

    @property
    def total_matches(self) -> int:
        return sum(m.count for m in self.matches)

    @property
    def matched_keywords(self) -> list[str]:
        return [m.keyword for m in self.matches if m.count > 0]


def extract_context(text: str, keyword: str, max_snippets: int = 2) -> list[str]:
    """Extract context snippets around keyword matches."""
    snippets = []
    pattern = re.compile(rf".{{0,40}}\b{re.escape(keyword)}\b.{{0,40}}", re.IGNORECASE)

    for match in pattern.finditer(text):
        snippet = match.group().strip()
        # Clean up the snippet
        snippet = re.sub(r"\s+", " ", snippet)
        if snippet:
            snippets.append(f"...{snippet}...")
            if len(snippets) >= max_snippets:
                break

    return snippets


def search_keywords(text: str, keywords: list[str]) -> list[SearchMatch]:
    """Search for keywords in text and return matches with context."""
    matches = []
    text_lower = text.lower()

    for keyword in keywords:
        # Use word boundaries for accurate matching
        pattern = rf"\b{re.escape(keyword.lower())}\b"
        count = len(re.findall(pattern, text_lower))

        if count > 0:
            context = extract_context(text, keyword)
            matches.append(SearchMatch(keyword=keyword, count=count, context_snippets=context))

    return sorted(matches, key=lambda m: m.count, reverse=True)


def fetch_page_content(page: CareerPage, no_js: bool = False) -> str:
    """Fetch content from a career page.
    
    Args:
        page: The career page to fetch
        no_js: If True, use static fetch (faster but may miss JS-loaded content)
    """
    if no_js:
        # Static fetch - faster but won't get JS-rendered content
        log(f"[{page.company}] Fetching with static request (--no-js)...")
        text = _fetch_with_requests(page.link)
        if text:
            log(f"[{page.company}] Got {len(text)} chars from static fetch")
        return text
    
    # Browser fetch - slower but gets JS-rendered content
    log(f"[{page.company}] Fetching with browser...")
    try:
        text = _fetch_with_playwright(page.link)
        log(f"[{page.company}] Got {len(text)} chars from browser")
        return text
    except Exception as e:
        log(f"[{page.company}] Browser fetch failed: {e}")
        # Fall back to static fetch as last resort
        log(f"[{page.company}] Trying static fetch...")
        text = _fetch_with_requests(page.link)
        if text:
            log(f"[{page.company}] Got {len(text)} chars from static fetch")
        return text


def scan_page(page: CareerPage, keywords: list[str], no_js: bool = False) -> PageScanResult:
    """Scan a single career page for keywords."""
    try:
        content = fetch_page_content(page, no_js=no_js)

        if not content:
            return PageScanResult(
                page=page,
                success=False,
                error_message="Failed to fetch page content",
            )

        matches = search_keywords(content, keywords)

        return PageScanResult(
            page=page,
            success=True,
            matches=matches,
            content_length=len(content),
        )

    except Exception as e:
        return PageScanResult(
            page=page,
            success=False,
            error_message=str(e),
        )


def scan_all_pages(config: SearchConfig) -> Iterator[PageScanResult]:
    """Scan all enabled pages and yield results."""
    for page in config.enabled_pages:
        keywords = config.get_keywords_for_page(page)
        yield scan_page(page, keywords)


def display_results(results: list[PageScanResult], verbose: bool = False) -> None:
    """Display scan results in a nice table format."""
    # Summary table
    table = Table(title="🔍 Career Page Search Results", show_header=True)
    table.add_column("Company", style="cyan", no_wrap=True)
    table.add_column("Status", style="dim")
    table.add_column("Matches", justify="right", style="green")
    table.add_column("Keywords Found", style="yellow")

    for result in results:
        if result.success:
            status = "✅"
            match_count = str(result.total_matches) if result.total_matches else "-"
            keywords_str = ", ".join(result.matched_keywords[:5])
            if len(result.matched_keywords) > 5:
                keywords_str += f" (+{len(result.matched_keywords) - 5})"
        else:
            status = f"❌ {result.error_message[:30]}"
            match_count = "-"
            keywords_str = "-"

        table.add_row(result.page.company, status, match_count, keywords_str)

    console.print()
    console.print(table)

    # Detailed results for pages with matches
    interesting_results = [r for r in results if r.success and r.total_matches > 0]

    if interesting_results and verbose:
        console.print()
        console.print("[bold]📋 Detailed Matches[/bold]")
        console.print()

        for result in interesting_results:
            console.print(f"[bold cyan]{result.page.company}[/bold cyan] ({result.page.link})")
            for match in result.matches:
                console.print(f"  • [yellow]{match.keyword}[/yellow]: {match.count} occurrences")
                for snippet in match.context_snippets:
                    console.print(f"    [dim]{snippet}[/dim]")
            console.print()


# -------------------------
# CLI Commands
# -------------------------
@app.command(name="search")
def search_pages(
    config_path: str = typer.Option(
        None, "--config", "-c", help="Path to job-search.toml config file"
    ),
    keywords: list[str] = typer.Option(
        None, "--keyword", "-k", help="Additional keywords to search (can be repeated)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed match context"),
    companies: list[str] = typer.Option(
        None, "--company", help="Search only these companies (can be repeated)"
    ),
    no_js: bool = typer.Option(
        False, "--no-js", help="Fast mode: skip JavaScript rendering (may miss dynamic content)"
    ),
) -> None:
    """
    Search configured career pages for job keywords.

    Reads career pages from job-search.toml and searches for configured keywords.
    """
    from pathlib import Path

    # Load configuration
    try:
        config = load_config(Path(config_path) if config_path else None)
    except FileNotFoundError as e:
        error(str(e))
        raise typer.Exit(1)
    except ValueError as e:
        error(str(e))
        raise typer.Exit(1)

    # Add CLI keywords to defaults
    if keywords:
        config.default_keywords.extend(keywords)

    # Filter to specific pages if requested
    if companies:
        matching_pages = [
            p for p in config.enabled_pages
            if any(c.lower() in p.company.lower() for c in companies)
        ]
        if not matching_pages:
            error(f"No pages found matching: {', '.join(companies)}")
            console.print("[dim]Available companies:[/dim]")
            for p in config.enabled_pages:
                console.print(f"  • {p.company}")
            raise typer.Exit(1)
        config.pages = matching_pages

    if not config.enabled_pages:
        error("No pages configured in job-search.toml")
        raise typer.Exit(1)

    console.print(f"[dim]Config: {config.config_path}[/dim]")
    console.print(f"[dim]Searching {len(config.enabled_pages)} page(s)...[/dim]")
    console.print()

    # Scan with progress
    results = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("Searching...", total=len(config.enabled_pages))

        for page in config.enabled_pages:
            progress.update(task, description=f"Searching in {page.company}...")
            page_keywords = config.get_keywords_for_page(page)
            result = scan_page(page, page_keywords, no_js=no_js)
            results.append(result)
            progress.advance(task)

    # Display results
    display_results(results, verbose=verbose)

    # Summary
    total_matches = sum(r.total_matches for r in results)
    successful = sum(1 for r in results if r.success)

    console.print()
    console.print(
        f"[bold]Summary:[/bold] {successful}/{len(results)} pages searched, "
        f"{total_matches} total keyword matches"
    )
