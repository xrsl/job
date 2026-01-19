"""Page fetching strategies."""

from job.fetchers.base import PageFetcher
from job.fetchers.browser import BrowserFetcher
from job.fetchers.static import StaticFetcher

__all__ = ["PageFetcher", "StaticFetcher", "BrowserFetcher"]
