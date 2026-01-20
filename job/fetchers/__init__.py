"""Page fetching strategies."""

from job.fetchers.base import AsyncPageFetcher, PageFetcher
from job.fetchers.browser import AsyncBrowserFetcher, BrowserFetcher
from job.fetchers.static import StaticFetcher

__all__ = [
    "PageFetcher",
    "AsyncPageFetcher",
    "StaticFetcher",
    "BrowserFetcher",
    "AsyncBrowserFetcher",
]
