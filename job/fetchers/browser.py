"""Browser-based page fetcher using Playwright (sync and async)."""

import subprocess
import sys

from playwright.async_api import async_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright
from structlog.typing import FilteringBoundLogger

from job.core.logging import get_logger
from job.fetchers.base import FetchResult


class BrowserFetcher:
    """Fetch page content using Playwright sync API (for CLI commands)."""

    def __init__(
        self,
        timeout_ms: int = 30000,
        wait_time_ms: int = 8000,
        logger: FilteringBoundLogger | None = None,
    ):
        """
        Initialize browser fetcher.

        Args:
            timeout_ms: Page load timeout in milliseconds
            wait_time_ms: Additional wait time for dynamic content
            logger: Optional structlog logger
        """
        self.timeout_ms = timeout_ms
        self.wait_time_ms = wait_time_ms
        self.logger = logger or get_logger()
        self._ensure_browser_installed()

    def _ensure_browser_installed(self) -> None:
        """Ensure Playwright browser is installed."""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
        except Exception as e:
            self.logger.info("browser_not_available", error=str(e))
            self.logger.info("installing_browser")
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to install browser: {result.stderr}")

    def fetch(self, url: str) -> FetchResult:
        """
        Fetch page content using Playwright.

        Args:
            url: The URL to fetch

        Returns:
            Extracted text content from the page

        Raises:
            PlaywrightTimeout: If page load times out
            Exception: For other fetch failures
        """
        self.logger.debug("fetching_browser", url=url)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
                page.wait_for_timeout(self.wait_time_ms)
                text = page.inner_text("body")
                title = page.title()
                browser.close()
                self.logger.debug("fetch_complete", chars=len(text), title=title)
                return FetchResult(content=text, title=title)
        except PlaywrightTimeout:
            self.logger.error("page_timeout", timeout_ms=self.timeout_ms)
            raise
        except Exception as e:
            self.logger.error("browser_fetch_failed", error=str(e))
            raise


class AsyncBrowserFetcher:
    """Fetch page content using Playwright async API (for concurrent operations)."""

    def __init__(
        self,
        timeout_ms: int = 30000,
        wait_time_ms: int = 8000,
        logger: FilteringBoundLogger | None = None,
    ):
        """
        Initialize async browser fetcher.

        Args:
            timeout_ms: Page load timeout in milliseconds
            wait_time_ms: Additional wait time for dynamic content
            logger: Optional structlog logger
        """
        self.timeout_ms = timeout_ms
        self.wait_time_ms = wait_time_ms
        self.logger = logger or get_logger()

    async def fetch(self, url: str) -> FetchResult:
        """
        Fetch page content using Playwright async API.

        Args:
            url: The URL to fetch

        Returns:
            Extracted text content from the page

        Raises:
            PlaywrightTimeout: If page load times out
            Exception: For other fetch failures
        """
        self.logger.debug("fetching_browser_async", url=url)
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
                await page.wait_for_timeout(self.wait_time_ms)
                text = await page.inner_text("body")
                title = await page.title()
                await browser.close()
                self.logger.debug("fetch_complete", chars=len(text), title=title)
                return FetchResult(content=text, title=title)
        except PlaywrightTimeout:
            self.logger.error("page_timeout", timeout_ms=self.timeout_ms)
            raise
        except Exception as e:
            self.logger.error("browser_fetch_failed", error=str(e))
            raise
