"""Application context for dependency injection."""

from dataclasses import dataclass, field
from functools import cached_property

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine
from structlog.typing import FilteringBoundLogger

from job.config import Settings
from job.core.logging import configure_logging, get_logger


@dataclass
class AppContext:
    """Application context holding shared dependencies."""

    config: Settings
    _logging_configured: bool = field(default=False, init=False)

    @cached_property
    def engine(self) -> Engine:
        """Lazy initialization of database engine."""
        db_path = self.config.get_db_path()
        self.logger.debug("initializing_database", path=str(db_path))
        engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(engine)
        return engine

    @cached_property
    def logger(self) -> FilteringBoundLogger:
        """Get configured structlog logger."""
        if not self._logging_configured:
            configure_logging(verbose=self.config.verbose)
            object.__setattr__(self, "_logging_configured", True)
        return get_logger()
