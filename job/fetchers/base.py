"""Base protocol for page fetchers."""

from typing import Protocol


class PageFetcher(Protocol):
    """Protocol for fetching page content."""

    def fetch(self, url: str) -> str:
        """
        Fetch page content from URL.

        Args:
            url: The URL to fetch

        Returns:
            The text content of the page

        Raises:
            Exception: If fetching fails
        """
        ...
