"""Browser-based page fetcher using Playwright."""

import logging
import subprocess
import sys

from playwright.sync_api import (
    TimeoutError as PlaywrightTimeout,
    sync_playwright,
)


class BrowserFetcher:
    """Fetch page content using Playwright (for JavaScript-heavy pages)."""

    def __init__(
        self,
        timeout_ms: int = 30000,
        wait_time_ms: int = 8000,
        logger: logging.Logger | None = None,
    ):
        """
        Initialize browser fetcher.

        Args:
            timeout_ms: Page load timeout in milliseconds
            wait_time_ms: Additional wait time for dynamic content
            logger: Optional logger for debug output
        """
        self.timeout_ms = timeout_ms
        self.wait_time_ms = wait_time_ms
        self.logger = logger or logging.getLogger(__name__)
        self._ensure_browser_installed()

    def _ensure_browser_installed(self) -> None:
        """Ensure Playwright browser is installed."""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                browser.close()
        except Exception as e:
            self.logger.info(f"Browser not available: {e}")
            self.logger.info("Installing browser (first-time setup)...")
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise RuntimeError(f"Failed to install browser: {result.stderr}")

    def fetch(self, url: str) -> str:
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
        self.logger.debug(f"Fetching with Playwright: {url}")
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
                # Wait for dynamic content to load
                page.wait_for_timeout(self.wait_time_ms)
                text = page.inner_text("body")
                browser.close()
                self.logger.debug(f"Fetched {len(text)} characters")
                return text
        except PlaywrightTimeout:
            self.logger.error(f"Page load timed out after {self.timeout_ms}ms")
            raise
        except Exception as e:
            self.logger.error(f"Browser fetch failed: {e}")
            raise
