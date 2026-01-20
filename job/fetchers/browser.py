"""Browser-based page fetcher using Playwright (sync and async)."""

import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright
from structlog.typing import FilteringBoundLogger

from job.core.logging import get_logger
from job.fetchers.base import FetchResult


def get_chrome_user_data_dir() -> Path | None:
    """Get the Chrome user data directory for the current OS."""
    import platform

    system = platform.system()

    if system == "Darwin":  # macOS
        path = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    elif system == "Linux":
        path = Path.home() / ".config" / "google-chrome"
    elif system == "Windows":
        local_app_data = Path.home() / "AppData" / "Local"
        path = local_app_data / "Google" / "Chrome" / "User Data"
    else:
        return None

    return path if path.exists() else None


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

    def _fetch_with_profile(self, url: str) -> FetchResult | None:
        """Try to fetch using Chrome user profile for logged-in sessions."""
        chrome_dir = get_chrome_user_data_dir()
        if not chrome_dir:
            self.logger.debug("chrome_profile_not_found")
            return None

        self.logger.debug("fetching_with_profile", profile=str(chrome_dir))
        try:
            with sync_playwright() as p:
                # Use persistent context with Chrome's user data
                # Note: Chrome must be closed for this to work
                context = p.chromium.launch_persistent_context(
                    user_data_dir=str(chrome_dir),
                    headless=True,
                    channel="chrome",  # Use installed Chrome
                    timeout=2000,  # Fail fast if profile is locked
                )
                page = context.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                page.wait_for_timeout(self.wait_time_ms)
                text = page.inner_text("body")
                title = page.title()
                context.close()
                self.logger.debug(
                    "profile_fetch_complete", chars=len(text), title=title
                )
                return FetchResult(content=text, title=title)
        except Exception as e:
            # Profile fetch failed (e.g., Chrome is open, profile locked)
            self.logger.debug("profile_fetch_failed", error=str(e))
            return None

    def _fetch_fresh(self, url: str) -> FetchResult:
        """Fetch using a fresh browser instance (no profile)."""
        self.logger.debug("fetching_browser_fresh", url=url)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            page.wait_for_timeout(self.wait_time_ms)
            text = page.inner_text("body")
            title = page.title()
            browser.close()
            self.logger.debug("fresh_fetch_complete", chars=len(text), title=title)
            return FetchResult(content=text, title=title)

    def fetch(self, url: str) -> FetchResult:
        """
        Fetch page content using Playwright.

        Tries to use Chrome profile first for logged-in sessions,
        falls back to fresh browser if profile unavailable.

        Args:
            url: The URL to fetch

        Returns:
            Extracted text content from the page

        Raises:
            PlaywrightTimeout: If page load times out
            Exception: For other fetch failures
        """
        self.logger.debug("fetching_browser", url=url)

        # Try profile-based fetch first
        result = self._fetch_with_profile(url)
        if result:
            return result

        # Fall back to fresh browser
        try:
            return self._fetch_fresh(url)
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

    async def _fetch_with_profile(self, url: str) -> FetchResult | None:
        """Try to fetch using Chrome user profile for logged-in sessions."""
        chrome_dir = get_chrome_user_data_dir()
        if not chrome_dir:
            self.logger.debug("chrome_profile_not_found")
            return None

        self.logger.debug("fetching_with_profile_async", profile=str(chrome_dir))
        try:
            async with async_playwright() as p:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=str(chrome_dir),
                    headless=True,
                    channel="chrome",
                    timeout=2000,  # Fail fast if profile is locked
                )
                page = await context.new_page()
                await page.goto(
                    url, wait_until="domcontentloaded", timeout=self.timeout_ms
                )
                await page.wait_for_timeout(self.wait_time_ms)
                text = await page.inner_text("body")
                title = await page.title()
                await context.close()
                self.logger.debug(
                    "profile_fetch_complete", chars=len(text), title=title
                )
                return FetchResult(content=text, title=title)
        except Exception as e:
            self.logger.debug("profile_fetch_failed", error=str(e))
            return None

    async def _fetch_fresh(self, url: str) -> FetchResult:
        """Fetch using a fresh browser instance (no profile)."""
        self.logger.debug("fetching_browser_fresh_async", url=url)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
            await page.wait_for_timeout(self.wait_time_ms)
            text = await page.inner_text("body")
            title = await page.title()
            await browser.close()
            self.logger.debug("fresh_fetch_complete", chars=len(text), title=title)
            return FetchResult(content=text, title=title)

    async def fetch(self, url: str) -> FetchResult:
        """
        Fetch page content using Playwright async API.

        Tries to use Chrome profile first for logged-in sessions,
        falls back to fresh browser if profile unavailable.

        Args:
            url: The URL to fetch

        Returns:
            Extracted text content from the page

        Raises:
            PlaywrightTimeout: If page load times out
            Exception: For other fetch failures
        """
        self.logger.debug("fetching_browser_async", url=url)

        # Try profile-based fetch first
        result = await self._fetch_with_profile(url)
        if result:
            return result

        # Fall back to fresh browser
        try:
            return await self._fetch_fresh(url)
        except PlaywrightTimeout:
            self.logger.error("page_timeout", timeout_ms=self.timeout_ms)
            raise
        except Exception as e:
            self.logger.error("browser_fetch_failed", error=str(e))
            raise
