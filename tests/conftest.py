"""Pytest configuration and fixtures."""

import pytest
from pathlib import Path
from sqlmodel import Session, SQLModel

from job.core import AppContext, Config, JobAd


@pytest.fixture
def test_db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path for testing."""
    return tmp_path / "test_jobs.db"


@pytest.fixture
def test_config(test_db_path: Path) -> Config:
    """Provide test configuration."""
    return Config(
        model="gemini-2.5-flash",
        db_path=test_db_path,
        search_config_path=None,
        verbose=False,
    )


@pytest.fixture
def app_context(test_config: Config) -> AppContext:
    """Provide application context for testing."""
    return AppContext(config=test_config)


@pytest.fixture
def db_session(app_context: AppContext):
    """Provide a database session for testing."""
    # Create tables
    SQLModel.metadata.create_all(app_context.engine)

    with Session(app_context.engine) as session:
        yield session

    # Cleanup
    SQLModel.metadata.drop_all(app_context.engine)


@pytest.fixture
def sample_job() -> JobAd:
    """Provide a sample job for testing."""
    return JobAd(
        job_posting_url="https://example.com/job/123",
        title="Senior Python Engineer",
        company="Example Corp",
        location="Copenhagen, Denmark",
        deadline="2024-12-31",
        department="Engineering",
        hiring_manager="Jane Doe",
        job_ad="We are looking for a senior Python engineer...",
    )
