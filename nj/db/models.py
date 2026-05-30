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


class JobEnrichmentORM(Base):
    __tablename__ = "job_enrichments"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    sponsorship_prob: Mapped[float | None] = mapped_column(Float, nullable=True)
    sponsorship_tier: Mapped[str | None] = mapped_column(String, nullable=True)
    predicted_salary: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_low: Mapped[int | None] = mapped_column(Integer, nullable=True)
    salary_high: Mapped[int | None] = mapped_column(Integer, nullable=True)
    semantic_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    uscis_petitions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uscis_approval_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    uscis_sponsor_tier: Mapped[str | None] = mapped_column(String, nullable=True)
    enriched_at: Mapped[datetime] = mapped_column(DateTime)


class GraphNodeORM(Base):
    __tablename__ = "graph_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    node_type: Mapped[str] = mapped_column(String, index=True)
    label: Mapped[str] = mapped_column(String, index=True)
    label_normalized: Mapped[str] = mapped_column(String, index=True)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String, default="manual")


class GraphEdgeORM(Base):
    __tablename__ = "graph_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_node_id: Mapped[int] = mapped_column(Integer, index=True)
    to_node_id: Mapped[int] = mapped_column(Integer, index=True)
    edge_type: Mapped[str] = mapped_column(String, index=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    source: Mapped[str] = mapped_column(String, default="manual")


class H1BPetitionORM(Base):
    __tablename__ = "h1b_petitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    employer_name: Mapped[str] = mapped_column(String, index=True)
    employer_name_normalized: Mapped[str] = mapped_column(String, index=True)
    job_title: Mapped[str] = mapped_column(String)
    job_title_normalized: Mapped[str] = mapped_column(String)
    wage_from: Mapped[float | None] = mapped_column(Float, nullable=True)
    wage_to: Mapped[float | None] = mapped_column(Float, nullable=True)
    wage_unit: Mapped[str] = mapped_column(String, default="year")
    case_status: Mapped[str] = mapped_column(String)
    year: Mapped[int] = mapped_column(Integer, index=True)
    worksite_state: Mapped[str] = mapped_column(String, default="")
    worksite_city: Mapped[str] = mapped_column(String, default="")
    is_ml_role: Mapped[bool] = mapped_column(Boolean, default=False)
    source_file: Mapped[str] = mapped_column(String, default="")


class CompanyIntelORM(Base):
    __tablename__ = "company_intel"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    name_normalized: Mapped[str] = mapped_column(String, index=True)
    total_petitions: Mapped[int] = mapped_column(Integer, default=0)
    approved_petitions: Mapped[int] = mapped_column(Integer, default=0)
    denied_petitions: Mapped[int] = mapped_column(Integer, default=0)
    ml_ai_petitions: Mapped[int] = mapped_column(Integer, default=0)
    median_salary: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_salary: Mapped[float | None] = mapped_column(Float, nullable=True)
    approval_rate: Mapped[float] = mapped_column(Float, default=0.0)
    sponsor_tier: Mapped[str] = mapped_column(String, default="UNKNOWN")
    last_updated: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    years_active: Mapped[list] = mapped_column(JSON, default=list)
    top_roles: Mapped[list] = mapped_column(JSON, default=list)
    states: Mapped[list] = mapped_column(JSON, default=list)
