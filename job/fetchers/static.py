"""Static page fetcher using requests."""

import requests
from bs4 import BeautifulSoup
from structlog.typing import FilteringBoundLogger

from job.core.logging import get_logger
from job.fetchers.base import FetchResult


class StaticFetcher:
    """Fetch page content using requests (for static pages)."""

    def __init__(self, timeout: int = 15, logger: FilteringBoundLogger | None = None):
        """
        Initialize static fetcher.

        Args:
            timeout: Request timeout in seconds
            logger: Optional structlog logger
        """
        self.timeout = timeout
        self.logger = logger or get_logger()

    def fetch(self, url: str) -> FetchResult:
        """
        Fetch page content using requests.

        Args:
            url: The URL to fetch

        Returns:
            Extracted text content from the page

        Raises:
            requests.RequestException: If the request fails
        """
        self.logger.debug("fetching_static", url=url)
        try:
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            if soup.body:
                text = soup.body.get_text(separator="\n", strip=True)
            else:
                text = soup.get_text(separator="\n", strip=True)
            title = soup.title.string if soup.title else None
            self.logger.debug("fetch_complete", chars=len(text), title=title)
            return FetchResult(content=text, title=title)
        except requests.Timeout:
            self.logger.warning("request_timeout", timeout_seconds=self.timeout)
            raise
        except requests.RequestException as e:
            self.logger.error("request_failed", error=str(e))
            raise
