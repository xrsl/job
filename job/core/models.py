"""Database models for job postings."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class JobAdBase(SQLModel):
    """Base schema for AI extraction (no DB metadata)."""

    job_posting_url: str
    title: str
    company: str
    location: str
    deadline: str
    department: str
    hiring_manager: str
    full_ad: str


class JobAd(JobAdBase, table=True):
    """Database table model with indexes for performance."""

    id: int | None = Field(default=None, primary_key=True)
    job_posting_url: str = Field(index=True, unique=True)
    title: str = Field(index=True)
    company: str = Field(index=True)
    location: str = Field(index=True)

    fit_assessments: list["JobFitAssessment"] = Relationship(back_populates="job")


class JobFitAssessmentBase(SQLModel):
    """Base schema for AI fit assessment (no DB metadata)."""

    overall_fit_score: int = Field(
        description="Overall fit score from 0-100. 80-100=excellent, 60-79=good, 40-59=moderate, 0-39=poor",
        ge=0,
        le=100,
    )
    fit_summary: str = Field(
        description="2-3 sentence summary of the candidate's overall fit for this role"
    )
    strengths: list[str] = Field(
        description="List of specific qualifications, experiences, and skills that match the job well. Each item is a concise statement (1-2 sentences)."
    )
    gaps: list[str] = Field(
        description="List of missing qualifications, skills, or experiences that the job requires. Each item is a concise statement (1-2 sentences)."
    )
    recommendations: str = Field(
        description="Specific, actionable advice on how to strengthen the application, address gaps, highlight relevant experience, and prepare for interviews"
    )
    key_insights: str = Field(
        description="Notable observations about the match: timing considerations, unique angles, red flags, growth opportunities, cultural alignment, etc."
    )


class JobFitAssessment(JobFitAssessmentBase, table=True):
    """Database table for job fit assessments."""

    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobad.id", index=True)
    model_name: str = Field(index=True)
    context_file_paths: str  # JSON array of paths
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), index=True
    )

    # Override to store as JSON strings in database
    strengths: str  # JSON array of strength statements
    gaps: str  # JSON array of gap statements

    job: Optional["JobAd"] = Relationship(back_populates="fit_assessments")
