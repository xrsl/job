"""Core domain models and configuration."""

from job.config import Settings
from job.core.context import AppContext
from job.core.logging import get_logger
from job.core.models import JobAd, JobAdBase, JobFitAssessment, JobFitAssessmentBase

# Backwards compatibility alias
Config = Settings

__all__ = [
    "Settings",
    "Config",  # Backwards compatibility
    "AppContext",
    "JobAd",
    "JobAdBase",
    "JobFitAssessment",
    "JobFitAssessmentBase",
    "get_logger",
]
