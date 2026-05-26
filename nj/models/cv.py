from __future__ import annotations

from pydantic import BaseModel


class Experience(BaseModel):
    id: str
    title: str
    company: str
    location: str
    start: str
    end: str
    status: str = "ended"
    bullets: list[str] = []
    bullets_pending: bool = False
    tags: list[str] = []


class Project(BaseModel):
    id: str
    name: str
    tech: list[str] = []
    date: str = ""
    priority: int = 99
    anchor: bool = False
    tags: list[str] = []
    bullets: list[str] = []
    bullets_pending: bool = False


class CVBase(BaseModel):
    personal: dict = {}
    summary: str = ""
    education: list[dict] = []
    skills: dict = {}
    experience: list[Experience] = []
    projects: list[Project] = []
    certifications: list[dict] = []
    memberships: list[dict] = []
    research_interests: list[str] = []
    soft_skills: list[str] = []
    gap_explanation: dict | None = None
    tailoring_rules: dict = {}
