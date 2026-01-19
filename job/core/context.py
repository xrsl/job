"""Application context for dependency injection."""

import logging
from dataclasses import dataclass
from functools import cached_property

from sqlalchemy.engine import Engine
from sqlmodel import SQLModel, create_engine

from job.core.config import Config


@dataclass
class AppContext:
    """Application context holding shared dependencies."""

    config: Config

    @cached_property
    def engine(self) -> Engine:
        """Lazy initialization of database engine."""
        self.logger.debug(f"Initializing database: {self.config.db_path}")
        engine = create_engine(f"sqlite:///{self.config.db_path}")
        SQLModel.metadata.create_all(engine)
        return engine

    @cached_property
    def logger(self) -> logging.Logger:
        """Get configured logger."""
        logger = logging.getLogger("job")
        if self.config.verbose:
            logger.setLevel(logging.DEBUG)
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
            logger.addHandler(handler)
        return logger
