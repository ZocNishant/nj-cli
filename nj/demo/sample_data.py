from __future__ import annotations

SAMPLE_JOB = {
    "id": "demo-job-001",
    "title": "Machine Learning Engineer",
    "company": "Acme AI",
    "url": "https://example.com/jobs/ml-engineer",
    "description": (
        "We are looking for a Machine Learning Engineer to join our "
        "computer vision team. You will build and deploy models for "
        "medical image analysis. H1B sponsorship available for the "
        "right candidate.\n\n"
        "Requirements:\n"
        "- 2+ years ML experience\n"
        "- Strong PyTorch skills\n"
        "- Experience with CNNs and transfer learning\n"
        "- Medical imaging or healthcare domain preferred\n"
        "- Docker and FastAPI for model serving\n"
        "- Grad-CAM or similar interpretability methods a plus\n\n"
        "Nice to have:\n"
        "- MLflow or W&B for experiment tracking\n"
        "- Kubernetes for deployment\n"
        "- Published research or strong GitHub projects"
    ),
    "location": "Remote (USA)",
    "source": "remoteok",
    "visa_label": "confirmed",
    "salary_raw": "$140,000 - $180,000",
}

SAMPLE_SCORE = {
    "total_score": 81,
    "confidence": 0.87,
    "sub_scores": [
        {
            "category": "skills_match",
            "score": 88,
            "weight": 0.30,
            "rationale": "PyTorch, EfficientNet, ViT, Grad-CAM all present — strong overlap",
            "evidence": ["PyTorch skills", "Grad-CAM interpretability"],
        },
        {
            "category": "experience_relevance",
            "score": 62,
            "weight": 0.25,
            "rationale": "GastroVision directly relevant; IT roles drag score",
            "evidence": ["medical image analysis", "computer vision team"],
        },
        {
            "category": "role_alignment",
            "score": 81,
            "weight": 0.20,
            "rationale": "CV engineer targeting ML role — strong trajectory match",
            "evidence": ["ML Engineer", "computer vision"],
        },
        {
            "category": "sponsorship_compatibility",
            "score": 95,
            "weight": 0.15,
            "rationale": "H1B sponsorship explicitly offered",
            "evidence": ["H1B sponsorship available"],
        },
        {
            "category": "location_fit",
            "score": 90,
            "weight": 0.05,
            "rationale": "Remote USA — ideal for OPT candidate",
            "evidence": ["Remote (USA)"],
        },
        {
            "category": "resume_strength",
            "score": 74,
            "weight": 0.05,
            "rationale": "Strong project anchor; work history needs reframing",
            "evidence": [],
        },
    ],
    "matched_skills": [
        "PyTorch",
        "EfficientNet",
        "ViT",
        "Grad-CAM",
        "Transfer Learning",
        "Docker",
    ],
    "missing_skills": ["MLflow", "Kubernetes", "W&B"],
    "recommended_emphasis": [
        "GastroVision project",
        "medical imaging domain",
        "Grad-CAM interpretability",
    ],
    "visa_compatible": True,
    "visa_notes": "H1B sponsorship explicitly available — strong match for OPT candidate.",
    "overall_rationale": (
        "Strong technical match on CV skills with GastroVision being directly "
        "relevant to medical image analysis. Main drag is work history reading "
        "as IT support rather than ML engineering. Sponsorship confirmed."
    ),
}

SAMPLE_DIAGNOSIS = {
    "overall_health": "moderate",
    "critical_issues": [
        {
            "section": "experience",
            "issue": "IT support roles (USD, Triad, CHOICE) dominate work history — recruiter sees sysadmin not ML engineer",
            "severity": "high",
            "fix": "Rewrite each IT bullet to lead with a quantified outcome or system impact, not a task description",
        },
        {
            "section": "summary",
            "issue": "No summary section — recruiter has no 15-second framing to anchor on",
            "severity": "high",
            "fix": "Add 3-line summary: ML engineer with medical imaging focus, GastroVision project, incoming Moffitt internship",
        },
        {
            "section": "skills",
            "issue": "Security tools (Wireshark, Metasploit, Kali) visible — signals wrong domain for ML roles",
            "severity": "medium",
            "fix": "Remove security tools section entirely for ML/CV applications — it creates noise",
        },
    ],
    "hidden_strengths": [
        "GastroVision: rare combination of clinical domain knowledge + state-of-the-art CV engineering",
        "Moffitt Cancer Center internship incoming — strongest signal of medical AI credibility",
        "EfficientNet + ViT ensemble is graduate-thesis quality work, not a tutorial project",
        "96.11% accuracy with class imbalance handling shows production-thinking, not just research",
    ],
    "weak_sections": ["experience", "summary"],
    "strong_sections": ["projects", "skills", "education"],
    "recruiter_first_impression": (
        "Sees an IT professional transitioning into ML. GastroVision saves it from the reject pile "
        "but the IT history creates doubt about ML depth. Would put in 'maybe' — not immediate reject, "
        "not immediate interview. The Moffitt internship, once added, changes this significantly."
    ),
    "ats_concerns": [
        "Employment gap 2022-2023 may trigger ATS filters",
        "Security tool keywords may mismatch ML role ATS profiles",
    ],
    "positioning_mismatch": (
        "CV is currently positioned as an IT professional who does ML projects on the side. "
        "Target roles want an ML engineer who has some IT background. The projects are strong "
        "enough to reposition — the work history framing is holding it back."
    ),
    "score_pattern_analysis": (
        "Experience relevance consistently lowest sub-score (avg ~55). "
        "Skills match consistently highest (avg ~85). "
        "Gap between skills and experience scores signals the positioning problem clearly."
    ),
    "top_recommendation": (
        "Add a 3-line summary section to the CV today. "
        "It is the single change with the highest immediate impact on recruiter first impression."
    ),
}

SAMPLE_GAPS = [
    {
        "skill": "mlflow",
        "frequency_pct": 68,
        "job_count": 41,
        "avg_score_when_missing": 71.2,
        "impact_score": 48.4,
        "estimated_score_boost": 8,
    },
    {
        "skill": "kubernetes",
        "frequency_pct": 54,
        "job_count": 32,
        "avg_score_when_missing": 69.8,
        "impact_score": 37.7,
        "estimated_score_boost": 6,
    },
    {
        "skill": "wandb",
        "frequency_pct": 41,
        "job_count": 25,
        "avg_score_when_missing": 72.1,
        "impact_score": 29.6,
        "estimated_score_boost": 4,
    },
    {
        "skill": "aws sagemaker",
        "frequency_pct": 38,
        "job_count": 23,
        "avg_score_when_missing": 68.4,
        "impact_score": 26.0,
        "estimated_score_boost": 4,
    },
    {
        "skill": "onnx",
        "frequency_pct": 22,
        "job_count": 13,
        "avg_score_when_missing": 74.3,
        "impact_score": 16.3,
        "estimated_score_boost": 2,
    },
]
