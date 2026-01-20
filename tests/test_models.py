"""Tests for database models."""

import pytest
from sqlmodel import Session, select

from job.core import JobAd


def test_job_ad_creation(sample_job: JobAd):
    """Test creating a JobAd instance."""
    assert sample_job.title == "Senior Python Engineer"
    assert sample_job.company == "Example Corp"
    assert sample_job.job_posting_url == "https://example.com/job/123"


def test_job_ad_database_operations(db_session: Session, sample_job: JobAd):
    """Test CRUD operations on JobAd."""
    # Create
    db_session.add(sample_job)
    db_session.commit()
    db_session.refresh(sample_job)

    assert sample_job.id is not None

    # Read
    job = db_session.exec(
        select(JobAd).where(JobAd.job_posting_url == sample_job.job_posting_url)
    ).first()
    assert job is not None
    assert job.title == "Senior Python Engineer"

    # Update
    job.title = "Staff Python Engineer"
    db_session.add(job)
    db_session.commit()

    updated_job = db_session.exec(select(JobAd).where(JobAd.id == job.id)).first()
    assert updated_job is not None
    assert updated_job.title == "Staff Python Engineer"

    # Delete
    db_session.delete(updated_job)
    db_session.commit()

    deleted_job = db_session.exec(select(JobAd).where(JobAd.id == job.id)).first()
    assert deleted_job is None


def test_job_ad_unique_constraint(db_session: Session, sample_job: JobAd):
    """Test that job_posting_url field has unique constraint."""
    db_session.add(sample_job)
    db_session.commit()

    # Try to add duplicate
    duplicate = JobAd(
        job_posting_url=sample_job.job_posting_url,
        title="Different Title",
        company="Different Company",
        location="Different Location",
        deadline="",
        department="",
        hiring_manager="",
        job_ad="",
    )

    db_session.add(duplicate)

    with pytest.raises(Exception):  # SQLite raises IntegrityError
        db_session.commit()
