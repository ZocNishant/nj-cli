from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from nj.db.engine import Base


class JobORM(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    company: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String)
    salary_raw: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String)
    visa_label: Mapped[str] = mapped_column(String, default="unknown")
    scraped_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String, default="new")
    description_hash: Mapped[str] = mapped_column(String)


class ScoreResultORM(Base):
    __tablename__ = "score_results"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    total_score: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)
    sub_scores: Mapped[dict] = mapped_column(JSON)
    matched_skills: Mapped[list] = mapped_column(JSON)
    missing_skills: Mapped[list] = mapped_column(JSON)
    recommended_emphasis: Mapped[list] = mapped_column(JSON)
    visa_compatible: Mapped[bool] = mapped_column(Boolean)
    visa_notes: Mapped[str] = mapped_column(String, default="")
    overall_rationale: Mapped[str] = mapped_column(Text, default="")
    scored_at: Mapped[datetime] = mapped_column(DateTime)
    provider: Mapped[str] = mapped_column(String, default="")
    prompt_version: Mapped[str] = mapped_column(String, default="")
    raw_response: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)


class ApplicationRecordORM(Base):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String, default="pending")
    cv_path: Mapped[str | None] = mapped_column(String, nullable=True)
    cover_letter_path: Mapped[str | None] = mapped_column(String, nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    screenshot_path: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    outcome_recorded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class JobLabelORM(Base):
    __tablename__ = "job_labels"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    label: Mapped[str] = mapped_column(String)
    user_rationale: Mapped[str | None] = mapped_column(String, nullable=True)
    labeled_at: Mapped[datetime] = mapped_column(DateTime)
    score_at_label_time: Mapped[int] = mapped_column(Integer, default=0)
