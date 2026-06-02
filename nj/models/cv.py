from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class VisaStatus(str, Enum):
    CITIZEN = "citizen"
    PERMANENT_RESIDENT = "permanent_resident"
    H1B = "h1b"
    OPT = "opt"
    CPT = "cpt"
    TN = "tn"
    O1 = "o1"
    WORK_PERMIT = "work_permit"
    STUDENT = "student"
    NOT_APPLICABLE = "not_applicable"
    OTHER = "other"


class CareerField(str, Enum):
    ML_AI = "ml_ai"
    SOFTWARE_ENGINEERING = "software_engineering"
    DATA_SCIENCE = "data_science"
    PRODUCT = "product"
    DESIGN = "design"
    RESEARCH = "research"
    DEVOPS_INFRA = "devops_infra"
    CYBERSECURITY = "cybersecurity"
    FINANCE_QUANT = "finance_quant"
    OTHER = "other"


class ExperienceStatus(str, Enum):
    ACTIVE = "active"
    ENDED = "ended"
    INCOMING = "incoming"
    FREELANCE = "freelance"
    VOLUNTEER = "volunteer"


class CVPersonal(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin: str = ""
    github: str = ""
    website: str = ""
    visa_status: str = VisaStatus.NOT_APPLICABLE
    work_authorization: str = ""
    graduation_date: str = ""
    target_country: str = "USA"


class CVExperience(BaseModel):
    id: str = ""
    title: str = ""
    company: str = ""
    start: str = ""
    end: str = ""
    status: str = ExperienceStatus.ACTIVE
    bullets: list[str] = []
    tags: list[str] = []
    location: str = ""


class CVProject(BaseModel):
    id: str = ""
    name: str = ""
    anchor: bool = False
    tech: list[str] = []
    bullets: list[str] = []
    priority: int = 1
    date: str = ""
    url: str = ""
    tags: list[str] = []


class CVEducation(BaseModel):
    degree: str = ""
    institution: str = ""
    start: str = ""
    end: str = ""
    gpa: str = ""
    courses: list[str] = []
    location: str = ""


class CVBase(BaseModel):
    personal: CVPersonal = CVPersonal()
    career_field: str = CareerField.SOFTWARE_ENGINEERING
    target_roles: list[str] = []
    target_locations: list[str] = []
    seniority: str = "mid"

    summary: str = ""
    skills: dict[str, list[str]] = {}
    experience: list[dict] = []
    projects: list[dict] = []
    education: list[dict] = []
    certifications: list[str] = []
    publications: list[str] = []
    languages: list[str] = []
    research_interests: list[str] = []
    soft_skills: list[str] = []

    cv_version: str = "1.0"
    created_at: str = ""
    last_updated: str = ""


# Legacy aliases — kept for backward compatibility
class Experience(CVExperience):
    id: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    start: str = ""
    end: str = ""
    status: str = "ended"
    bullets: list[str] = []
    bullets_pending: bool = False
    tags: list[str] = []


class Project(CVProject):
    id: str = ""
    name: str = ""
    tech: list[str] = []
    date: str = ""
    priority: int = 99
    anchor: bool = False
    tags: list[str] = []
    bullets: list[str] = []
    bullets_pending: bool = False
