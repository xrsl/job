# search.py
"""
Career page scanning functionality with async support.
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import typer
from rich.console import Console
from rich.table import Table

from job.core import AppContext
from job.fetchers import AsyncBrowserFetcher, BrowserFetcher, StaticFetcher
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


# Common date patterns found on career pages
DATE_PATTERNS = [
    # "Jan 15, 2026" or "January 15, 2026"
    (
        r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2}),?\s+(\d{4})\b",
        "%b %d %Y",
    ),
    # "15 Jan 2026" or "15 January 2026"
    (
        r"\b(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})\b",
        "%d %b %Y",
    ),
    # "2026-01-15" ISO format
    (r"\b(\d{4})-(\d{2})-(\d{2})\b", "%Y-%m-%d"),
    # "01/15/2026" US format
    (r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", "%m/%d/%Y"),
    # "15/01/2026" EU format
    (r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", "%d/%m/%Y"),
    # "Posted 2 days ago", "1 day ago"
    (r"\b(\d+)\s+days?\s+ago\b", "relative_days"),
    # "Posted today"
    (r"\btoday\b", "today"),
    # "Posted yesterday"
    (r"\byesterday\b", "yesterday"),
]


def parse_date_from_text(text: str) -> datetime | None:
    """Try to parse a date from text using common patterns."""
    text_lower = text.lower()

    # Handle relative dates
    if "today" in text_lower:
        return datetime.now()
    if "yesterday" in text_lower:
        return datetime.now() - timedelta(days=1)

    # "X days ago" pattern
    days_ago_match = re.search(r"(\d+)\s+days?\s+ago", text_lower)
    if days_ago_match:
        days = int(days_ago_match.group(1))
        return datetime.now() - timedelta(days=days)

    # Try standard date formats
    for pattern, date_format in DATE_PATTERNS:
        if date_format in ("relative_days", "today", "yesterday"):
            continue  # Already handled above

        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            date_str = match.group(0)
            # Normalize month names to 3-letter abbreviations for parsing
            for full, abbr in [
                ("january", "jan"),
                ("february", "feb"),
                ("march", "mar"),
                ("april", "apr"),
                ("june", "jun"),
                ("july", "jul"),
                ("august", "aug"),
                ("september", "sep"),
                ("october", "oct"),
                ("november", "nov"),
                ("december", "dec"),
            ]:
                date_str = re.sub(full, abbr, date_str, flags=re.IGNORECASE)

            # Remove comma if present
            date_str = date_str.replace(",", "")

            try:
                return datetime.strptime(date_str, date_format)
            except ValueError:
                continue

    return None


def is_content_within_days(text: str, days: int) -> bool:
    """Check if the text contains a date within the specified number of days."""
    cutoff_date = datetime.now() - timedelta(days=days)

    # Search in a wider context for dates
    parsed_date = parse_date_from_text(text)
    if parsed_date:
        return parsed_date >= cutoff_date

    # If no date found, include content (don't filter out)
    return True


def extract_context(
    text: str, keyword: str, max_snippets: int = 1000, since_days: int | None = None
) -> list[str]:
    """Extract context snippets around keyword matches.

    Args:
        text: The text to search in
        keyword: The keyword to find
        max_snippets: Maximum number of snippets to return
        since_days: If set, only include snippets with dates within this many days
    """
    snippets = []
    # Use wider context to capture dates
    context_size = 100 if since_days else 40
    pattern = re.compile(
        rf".{{0,{context_size}}}\b{re.escape(keyword)}\b.{{0,{context_size}}}",
        re.IGNORECASE,
    )

    for match in pattern.finditer(text):
        snippet = match.group().strip()
        # Clean up the snippet
        snippet = re.sub(r"\s+", " ", snippet)

        if snippet:
            # Filter by date if --since is specified
            if since_days is not None and not is_content_within_days(
                snippet, since_days
            ):
                continue

            # Trim to display size
            display_snippet = (
                snippet
                if len(snippet) <= 83
                else f"...{snippet[len(snippet) // 2 - 40 : len(snippet) // 2 + 40]}..."
            )
            snippets.append(f"...{display_snippet.strip('.')}...")
            if len(snippets) >= max_snippets:
                break

    return snippets


def search_keywords(
    text: str, keywords: list[str], since_days: int | None = None
) -> list[SearchMatch]:
    """Search for keywords in text and return matches with context.

    Args:
        text: The text to search in
        keywords: Keywords to search for
        since_days: If set, only include matches with dates within this many days
    """
    matches = []
    text_lower = text.lower()

    for keyword in keywords:
        # Use word boundaries for accurate matching
        pattern = rf"\b{re.escape(keyword.lower())}\b"
        count = len(re.findall(pattern, text_lower))

        if count > 0:
            context = extract_context(text, keyword, since_days=since_days)
            # Only add match if we have context (respects date filter)
            if context or since_days is None:
                matches.append(
                    SearchMatch(
                        keyword=keyword,
                        count=len(context) if since_days else count,
                        context_snippets=context,
                    )
                )

    return sorted(matches, key=lambda m: m.count, reverse=True)


def fetch_page_content(page: CareerPage, ctx: AppContext, no_js: bool = False) -> str:
    """Fetch content from a career page.

    Args:
        page: The career page to fetch
        ctx: Application context
        no_js: If True, use static fetch (faster but may miss JS-loaded content)
    """
    log = ctx.logger.bind(company=page.company)

    if no_js:
        log.debug("fetching_static")
        static_fetcher = StaticFetcher(
            timeout=ctx.config.REQUEST_TIMEOUT, logger=ctx.logger
        )
        result = static_fetcher.fetch(page.url)
        text = result.content
        if text:
            log.debug("static_fetch_complete", chars=len(text))
        return text

    # Browser fetch - slower but gets JS-rendered content
    log.debug("fetching_browser")
    try:
        browser_fetcher = BrowserFetcher(
            timeout_ms=ctx.config.PLAYWRIGHT_TIMEOUT_MS, logger=ctx.logger
        )
        result = browser_fetcher.fetch(page.url)
        text = result.content
        log.debug("browser_fetch_complete", chars=len(text))
        return text
    except Exception as e:
        log.warning("browser_fetch_failed", error=str(e))
        # Fall back to static fetch as last resort
        log.debug("fallback_static_fetch")
        static_fetcher = StaticFetcher(
            timeout=ctx.config.REQUEST_TIMEOUT, logger=ctx.logger
        )
        result = static_fetcher.fetch(page.url)
        text = result.content
        if text:
            log.debug("static_fetch_complete", chars=len(text))
        return text


def scan_page(
    page: CareerPage,
    keywords: list[str],
    ctx: AppContext,
    no_js: bool = False,
    since_days: int | None = None,
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

        matches = search_keywords(content, keywords, since_days=since_days)

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


async def fetch_page_content_async(
    page: CareerPage, ctx: AppContext, no_js: bool = False
) -> str:
    """Async fetch content from a career page using native async playwright.

    Args:
        page: The career page to fetch
        ctx: Application context
        no_js: If True, use static fetch (run in executor since requests is sync)
    """
    log = ctx.logger.bind(company=page.company)

    if no_js:
        # Static fetch - run sync requests in executor
        log.debug("fetching_static_async")
        static_fetcher = StaticFetcher(
            timeout=ctx.config.REQUEST_TIMEOUT, logger=ctx.logger
        )

        # Helper to run fetch and get content
        def _fetch():
            return static_fetcher.fetch(page.url).content

        text = await asyncio.to_thread(_fetch)
        if text:
            log.debug("static_fetch_complete", chars=len(text))
        return text

    # Browser fetch using native async playwright
    log.debug("fetching_browser_async")
    try:
        async_fetcher = AsyncBrowserFetcher(
            timeout_ms=ctx.config.PLAYWRIGHT_TIMEOUT_MS, logger=ctx.logger
        )
        result = await async_fetcher.fetch(page.url)
        text = result.content
        log.debug("browser_fetch_complete", chars=len(text))
        return text
    except Exception as e:
        log.warning("browser_fetch_failed", error=str(e))
        # Fall back to static fetch
        log.debug("fallback_static_fetch")
        static_fetcher = StaticFetcher(
            timeout=ctx.config.REQUEST_TIMEOUT, logger=ctx.logger
        )

        def _fetch():
            return static_fetcher.fetch(page.url).content

        text = await asyncio.to_thread(_fetch)
        if text:
            log.debug("static_fetch_complete", chars=len(text))
        return text


async def scan_page_async(
    page: CareerPage,
    keywords: list[str],
    ctx: AppContext,
    no_js: bool = False,
    since_days: int | None = None,
) -> PageScanResult:
    """Async scan a single career page for keywords using native async."""
    try:
        content = await fetch_page_content_async(page, ctx, no_js=no_js)

        if not content:
            return PageScanResult(
                page=page,
                success=False,
                error_message="Failed to fetch page content",
            )

        matches = search_keywords(content, keywords, since_days=since_days)

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


async def scan_all_pages_async(
    config: SearchConfig,
    ctx: AppContext,
    no_js: bool = False,
    since_days: int | None = None,
) -> list[PageScanResult]:
    """Scan all enabled pages concurrently using native async."""
    tasks = [
        scan_page_async(
            page, config.get_keywords_for_page(page), ctx, no_js, since_days
        )
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
                f"[bold cyan]{result.page.company}[/bold cyan] ({result.page.url})"
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
@app.command(name="s", hidden=True)
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
        "-p",
        help="Fetch pages in parallel (faster but uses more resources)",
    ),
    since: int = typer.Option(
        None,
        "--since",
        "-s",
        help="Only show jobs posted within this many days (filters by date in content)",
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
    if since:
        console.print(f"[bold]Since:[/bold] {since} day(s) ago")
    console.print()

    # Scan pages (parallel or sequential)
    if parallel:
        with console.status("[bold]Searching all pages in parallel...[/bold]"):
            results = asyncio.run(scan_all_pages_async(config, app_ctx, no_js, since))

        # Print matches after parallel scan completes
        for result in results:
            page = result.page
            console.print(f"[bold]Searching in {page.company}...[/bold]")
            positions_found = 0
            for match in result.matches:
                for snippet in match.context_snippets:
                    positions_found += 1
                    clean_snippet = snippet.strip(".")
                    console.print(
                        f"  [green]Found[/green] [yellow]{match.keyword}[/yellow] "
                        f"in [link={page.url}][cyan]{clean_snippet}[/cyan][/link]"
                    )
            if positions_found > 0:
                console.print(
                    f"  [bold]{positions_found} position(s) found in {page.company}[/bold]"
                )
            elif result.success:
                console.print(f"  [dim]No matches in {page.company}[/dim]")
    else:
        results = []
        total_pages = len(config.enabled_pages)

        for i, page in enumerate(config.enabled_pages, 1):
            with console.status(
                f"[bold]Searching in {page.company}...[/bold] ({i}/{total_pages})"
            ):
                page_keywords = config.get_keywords_for_page(page)
                result = scan_page(
                    page, page_keywords, app_ctx, no_js=no_js, since_days=since
                )
                results.append(result)

            # Print matches after fetching
            positions_found = 0
            for match in result.matches:
                for snippet in match.context_snippets:
                    positions_found += 1
                    clean_snippet = snippet.strip(".")
                    console.print(
                        f"  [green]Found[/green] [yellow]{match.keyword}[/yellow] "
                        f"in [link={page.url}][cyan]{clean_snippet}[/cyan][/link]"
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
