"""Configuration management for job CLI.

This module provides configuration loading from:
1. Environment variables (JOB_ prefix)
2. job.toml file (multiple locations)
3. Default values

All models are defined in settings.py which is the single source of truth.
JSON Schema is exported via generate_schema().
"""

from .settings import (
    CareerPage,
    JobAdd,
    JobApp,
    JobFit,
    JobGH,
    JobSearch,
    Settings,
    generate_schema,
    settings,
    write_schema,
)

__all__ = [
    "settings",
    "Settings",
    "CareerPage",
    "JobAdd",
    "JobApp",
    "JobFit",
    "JobGH",
    "JobSearch",
    "generate_schema",
    "write_schema",
]
