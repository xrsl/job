"""Static page fetcher using requests."""

import logging

import requests
from bs4 import BeautifulSoup


class StaticFetcher:
    """Fetch page content using requests (for static pages)."""

    def __init__(self, timeout: int = 15, logger: logging.Logger | None = None):
        """
        Initialize static fetcher.

        Args:
            timeout: Request timeout in seconds
            logger: Optional logger for debug output
        """
        self.timeout = timeout
        self.logger = logger or logging.getLogger(__name__)

    def fetch(self, url: str) -> str:
        """
        Fetch page content using requests.

        Args:
            url: The URL to fetch

        Returns:
            Extracted text content from the page

        Raises:
            requests.RequestException: If the request fails
        """
        self.logger.debug(f"Fetching with requests: {url}")
        try:
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            text = soup.get_text(separator="\n", strip=True)
            self.logger.debug(f"Fetched {len(text)} characters")
            return text
        except requests.Timeout:
            self.logger.warning(f"Request timed out after {self.timeout}s")
            raise
        except requests.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise
