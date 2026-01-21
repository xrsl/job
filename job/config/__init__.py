"""Configuration management for job CLI.

This module provides configuration loading from:
1. Environment variables (JOB_ prefix)
2. job.toml file (multiple locations)
3. Default values

Models are auto-generated from schema/schema.cue via `just models`.
Extended models with helpers are in extensions.py.
"""

from .config import Settings, settings
from .extensions import (
    CareerPage,
    JobAdd,
    JobExport,
    JobFit,
    JobGH,
    JobSearch,
    JobSettings,
)

# Backwards compatibility aliases
SearchSettings = JobSearch
GitHubSettings = JobGH
FitSettings = JobFit
AddSettings = JobAdd
ExportSettings = JobExport

__all__ = [
    "settings",
    "Settings",
    "CareerPage",
    "JobAdd",
    "JobExport",
    "JobFit",
    "JobGH",
    "JobSearch",
    "JobSettings",
    # Aliases
    "SearchSettings",
    "GitHubSettings",
    "FitSettings",
    "AddSettings",
    "ExportSettings",
]
