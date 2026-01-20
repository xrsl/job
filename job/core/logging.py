"""Structured logging configuration using structlog."""

import logging
import sys

import structlog
from structlog.typing import FilteringBoundLogger


def configure_logging(verbose: bool = False) -> None:
    """Configure structlog with pretty console output.

    Args:
        verbose: If True, set log level to DEBUG, otherwise INFO.
    """
    log_level = logging.DEBUG if verbose else logging.INFO

    # Configure standard logging for libraries
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=log_level,
    )

    # Configure structlog processors
    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Pretty console output for development
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None, **initial_context: str) -> FilteringBoundLogger:
    """Get a structlog logger with optional bound context.

    Args:
        name: Optional logger name (defaults to "job")
        **initial_context: Key-value pairs to bind to the logger

    Returns:
        A bound structlog logger instance

    Example:
        log = get_logger(company="ACME")
        log.info("Fetching page")  # Output includes company="ACME"
    """
    logger = structlog.get_logger(name or "job")
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger
