"""Job CLI - A tool to manage job postings."""

__version__ = "0.1.0"
__author__ = "xrsl"

from job.main import app, JobAd, JobAdBase

__all__ = ["app", "JobAd", "JobAdBase", "__version__"]
