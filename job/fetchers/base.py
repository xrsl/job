"""Base protocol for page fetchers."""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class FetchResult:
    """Result of a page fetch operation."""

    content: str
    title: str | None = None


class PageFetcher(Protocol):
    """Protocol for synchronous page fetching."""

    def fetch(self, url: str) -> FetchResult:
        """
        Fetch page content from URL.

        Args:
            url: The URL to fetch

        Returns:
            The fetch result containing content and metadata

        Raises:
            Exception: If fetching fails
        """
        ...


class AsyncPageFetcher(Protocol):
    """Protocol for asynchronous page fetching."""

    async def fetch(self, url: str) -> FetchResult:
        """
        Fetch page content from URL asynchronously.

        Args:
            url: The URL to fetch

        Returns:
            The fetch result containing content and metadata

        Raises:
            Exception: If fetching fails
        """
        ...
