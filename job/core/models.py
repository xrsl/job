"""Database models for job postings."""

from sqlmodel import Field, SQLModel


class JobAdBase(SQLModel):
    """Base schema for AI extraction (no DB metadata)."""

    job_posting: str
    title: str
    company: str
    location: str
    deadline: str
    department: str
    hiring_manager: str
    job_ad: str


class JobAd(JobAdBase, table=True):
    """Database table model with indexes for performance."""

    id: int | None = Field(default=None, primary_key=True)
    job_posting: str = Field(index=True, unique=True)
    title: str = Field(index=True)
    company: str = Field(index=True)
    location: str = Field(index=True)
