from typer.testing import CliRunner
from sqlmodel import Session, SQLModel
from job.main import app
from job.core import JobAd
import os
import pytest

runner = CliRunner()


@pytest.fixture
def test_db_env(tmp_path):
    """Set JOB_DB_PATH to a lookup in a temporary directory."""
    db_path = tmp_path / "test_commands.db"
    os.environ["JOB_DB_PATH"] = str(db_path)
    yield db_path
    if "JOB_DB_PATH" in os.environ:
        del os.environ["JOB_DB_PATH"]


@pytest.fixture
def prepopulated_db(test_db_env):
    """Create DB tables and add sample jobs."""
    # We need to manually initialize the engine because the app creates it
    # based on the config which reads the env var we just set.
    # However, for prepopulating, we can just use the path directly with sqlmodel.
    from sqlmodel import create_engine

    engine = create_engine(f"sqlite:///{test_db_env}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        job1 = JobAd(
            job_posting_url="https://example.com/1",
            title="Job One",
            company="Company A",
            location="City A",
            deadline="2025-01-01",
            department="Dep A",
            hiring_manager="Man A",
            full_ad="Ad Content 1",
        )
        job2 = JobAd(
            job_posting_url="https://example.com/2",
            title="Job Two",
            company="Company B",
            location="City B",
            deadline="2025-02-02",
            department="Dep B",
            hiring_manager="Man B",
            full_ad="Ad Content 2",
        )
        session.add(job1)
        session.add(job2)
        session.commit()
    return test_db_env


def test_ls_shows_ids(prepopulated_db):
    result = runner.invoke(app, ["ls"])
    assert result.exit_code == 0
    assert "ID" in result.output
    assert "Job One" in result.output
    assert "Job Two" in result.output
    # Check if IDs are present (1 and 2 usually, as sqlite starts at 1)
    assert "1" in result.output
    assert "2" in result.output


def test_view_by_id(prepopulated_db):
    result = runner.invoke(app, ["view", "1", "--json"])
    assert result.exit_code == 0
    assert "Job One" in result.output
    assert "https://example.com/1" in result.output


def test_view_by_url(prepopulated_db):
    result = runner.invoke(app, ["view", "https://example.com/2", "--json"])
    assert result.exit_code == 0
    assert "Job Two" in result.output


def test_del_by_id(prepopulated_db):
    # Remove job 1
    result = runner.invoke(app, ["del", "1"])
    assert result.exit_code == 0
    assert "Deleted job 1" in result.output

    # Verify gone
    result = runner.invoke(app, ["list"])
    assert "Job One" not in result.output
    assert "Job Two" in result.output


def test_export_by_id(prepopulated_db):
    result = runner.invoke(app, ["export", "2"])
    assert result.exit_code == 0
    assert "Job Two" in result.output
    assert "Job One" not in result.output


def test_export_invalid_id(prepopulated_db):
    result = runner.invoke(app, ["export", "999"])
    assert result.exit_code == 1
    assert "No job found" in result.output


def test_app_list_no_drafts(prepopulated_db):
    result = runner.invoke(app, ["app", "list"])
    assert result.exit_code == 0
    assert "No application drafts found" in result.output
