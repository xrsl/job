# search.py
"""
Career page scanning functionality with async support.
"""

import asyncio
import re
from dataclasses import dataclass, field

import typer
from rich.console import Console
from rich.table import Table

from job.core import AppContext
from job.fetchers import BrowserFetcher, StaticFetcher
from job.main import app, error
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


def extract_context(text: str, keyword: str, max_snippets: int = 1000) -> list[str]:
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
            matches.append(
                SearchMatch(keyword=keyword, count=count, context_snippets=context)
            )

    return sorted(matches, key=lambda m: m.count, reverse=True)


def fetch_page_content(page: CareerPage, ctx: AppContext, no_js: bool = False) -> str:
    """Fetch content from a career page.

    Args:
        page: The career page to fetch
        ctx: Application context
        no_js: If True, use static fetch (faster but may miss JS-loaded content)
    """
    if no_js:
        # Static fetch - faster but won't get JS-rendered content
        ctx.logger.debug(f"[{page.company}] Fetching with static request (--no-js)...")
        static_fetcher = StaticFetcher(
            timeout=ctx.config.REQUEST_TIMEOUT, logger=ctx.logger
        )
        text = static_fetcher.fetch(page.link)
        if text:
            ctx.logger.debug(
                f"[{page.company}] Got {len(text)} chars from static fetch"
            )
        return text

    # Browser fetch - slower but gets JS-rendered content
    ctx.logger.debug(f"[{page.company}] Fetching with browser...")
    try:
        browser_fetcher = BrowserFetcher(
            timeout_ms=ctx.config.PLAYWRIGHT_TIMEOUT_MS, logger=ctx.logger
        )
        text = browser_fetcher.fetch(page.link)
        ctx.logger.debug(f"[{page.company}] Got {len(text)} chars from browser")
        return text
    except Exception as e:
        ctx.logger.warning(f"[{page.company}] Browser fetch failed: {e}")
        # Fall back to static fetch as last resort
        ctx.logger.debug(f"[{page.company}] Trying static fetch...")
        static_fetcher = StaticFetcher(
            timeout=ctx.config.REQUEST_TIMEOUT, logger=ctx.logger
        )
        text = static_fetcher.fetch(page.link)
        if text:
            ctx.logger.debug(
                f"[{page.company}] Got {len(text)} chars from static fetch"
            )
        return text


def scan_page(
    page: CareerPage, keywords: list[str], ctx: AppContext, no_js: bool = False
) -> PageScanResult:
    """Scan a single career page for keywords."""
    try:
        content = fetch_page_content(page, ctx, no_js=no_js)

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


async def scan_page_async(
    page: CareerPage, keywords: list[str], ctx: AppContext, no_js: bool = False
) -> PageScanResult:
    """Async wrapper for scanning a page (runs sync code in executor)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, scan_page, page, keywords, ctx, no_js)


async def scan_all_pages_async(
    config: SearchConfig, ctx: AppContext, no_js: bool = False
) -> list[PageScanResult]:
    """Scan all enabled pages concurrently using asyncio."""
    tasks = [
        scan_page_async(page, config.get_keywords_for_page(page), ctx, no_js)
        for page in config.enabled_pages
    ]
    return await asyncio.gather(*tasks)


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

    # Detailed verbose output
    interesting_results = [r for r in results if r.success and r.total_matches > 0]
    if interesting_results and verbose:
        console.print()
        console.print("[bold]🔎 Detailed Matches[/bold]")
        console.print()

        for result in interesting_results:
            console.print(
                f"[bold cyan]{result.page.company}[/bold cyan] ({result.page.link})"
            )
            for match in result.matches:
                console.print(
                    f"  • [yellow]{match.keyword}[/yellow]: {match.count} occurrences"
                )
                for snippet in match.context_snippets:
                    console.print(f"    [dim]{snippet}[/dim]")
            console.print()


# -------------------------
# CLI Commands
# -------------------------
@app.command(name="search")
def search_pages(
    ctx: typer.Context,
    config_path: str = typer.Option(
        None, "--config", "-c", help="Path to job-search.toml config file"
    ),
    keywords: list[str] = typer.Option(
        None,
        "--keyword",
        "-k",
        help="Keywords to search (replaces defaults, can be repeated)",
    ),
    extra_keywords: list[str] = typer.Option(
        None,
        "--extra",
        "-e",
        help="Additional keywords to append to defaults (can be repeated)",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed match context"
    ),
    companies: list[str] = typer.Option(
        None, "--company", help="Search only these companies (can be repeated)"
    ),
    no_js: bool = typer.Option(
        False,
        "--no-js",
        help="Fast mode: skip JavaScript rendering (may miss dynamic content)",
    ),
    parallel: bool = typer.Option(
        False,
        "--parallel",
        help="Fetch pages in parallel (faster but uses more resources)",
    ),
) -> None:
    """
    Search configured career pages for job keywords.

    Reads career pages from job-search.toml and searches for configured keywords.
    """
    from pathlib import Path

    app_ctx: AppContext = ctx.obj

    # Load configuration
    try:
        config = load_config(Path(config_path) if config_path else None)
    except FileNotFoundError as e:
        error(str(e))
        raise typer.Exit(1)
    except ValueError as e:
        error(str(e))
        raise typer.Exit(1)

    # Handle keywords: --keyword replaces defaults, --extra appends
    if keywords:
        config.default_keywords = list(keywords)
    if extra_keywords:
        config.default_keywords.extend(extra_keywords)

    # Filter to specific pages if requested
    if companies:
        matching_pages = [
            p
            for p in config.enabled_pages
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

    # Show what we're searching
    console.print(f"[dim]Config: {config.config_path}[/dim]")
    company_names = ", ".join(p.company for p in config.enabled_pages)
    console.print(f"[bold]Companies:[/bold] {company_names}")
    keywords_str = ", ".join(config.default_keywords) or "[dim](none)[/dim]"
    console.print(f"[bold]Keywords:[/bold] {keywords_str}")
    console.print()

    # Scan pages (parallel or sequential)
    if parallel:
        console.print("[dim]Fetching pages in parallel...[/dim]")
        with console.status("[bold]Scanning all pages...[/bold]"):
            results = asyncio.run(scan_all_pages_async(config, app_ctx, no_js))
    else:
        results = []
        total_pages = len(config.enabled_pages)

        for i, page in enumerate(config.enabled_pages, 1):
            with console.status(
                f"[bold]Searching in {page.company}...[/bold] ({i}/{total_pages})"
            ):
                page_keywords = config.get_keywords_for_page(page)
                result = scan_page(page, page_keywords, app_ctx, no_js=no_js)
                results.append(result)

            # Print matches after fetching
            positions_found = 0
            for match in result.matches:
                for snippet in match.context_snippets:
                    positions_found += 1
                    clean_snippet = snippet.strip(".")
                    console.print(
                        f"  [green]Found[/green] [yellow]{match.keyword}[/yellow] "
                        f"in [link={page.link}][cyan]{clean_snippet}[/cyan][/link]"
                    )
            if positions_found > 0:
                console.print(
                    f"  [bold]{positions_found} position(s) found in {page.company}[/bold]"
                )
            elif result.success:
                console.print(f"  [dim]No matches in {page.company}[/dim]")

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
