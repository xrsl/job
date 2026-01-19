"""Job CLI - A tool to manage job postings."""

__version__ = "0.1.0"
__author__ = "xrsl"

from job.core import AppContext, Config, JobAd, JobAdBase
from job.main import app

__all__ = ["app", "AppContext", "Config", "JobAd", "JobAdBase", "__version__"]
