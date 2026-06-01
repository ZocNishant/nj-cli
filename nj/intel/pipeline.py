from __future__ import annotations

import csv
import io
import re
import zipfile
from pathlib import Path
from typing import Any

import httpx

from nj.utils.logger import get_logger

logger = get_logger(__name__)

USCIS_DATA_URLS: dict[int, str] = {
    2023: "https://www.uscis.gov/sites/default/files/document/data/h1b_datahubexport-2023.csv",
    2022: "https://www.uscis.gov/sites/default/files/document/data/h1b_datahubexport-2022.csv",
    2024: "https://www.uscis.gov/sites/default/files/document/data/h1b_datahubexport-2024.csv",
}

ML_AI_KEYWORDS: set[str] = {
    "machine learning",
    "ml engineer",
    "data scientist",
    "artificial intelligence",
    "deep learning",
    "nlp",
    "natural language",
    "computer vision",
    "research scientist",
    "ai engineer",
    "mlops",
    "applied scientist",
    "research engineer",
    "neural",
    "data engineer",
    "analytics engineer",
    "quantitative",
}

_NOISE = re.compile(r"\b(inc|llc|ltd|corp|corporation|co|the|a|an)\b\.?", re.I)
_SPACES = re.compile(r"\s+")


def normalize_company(name: str) -> str:
    s = name.lower().strip()
    s = _NOISE.sub(" ", s)
    s = _SPACES.sub(" ", s).strip()
    return s


def normalize_title(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[,\-/|]+", " ", s)
    s = _SPACES.sub(" ", s).strip()
    return s


def is_ml_role(title: str) -> bool:
    norm = normalize_title(title)
    return any(kw in norm for kw in ML_AI_KEYWORDS)


def parse_wage(wage_str: str | None) -> float | None:
    if not wage_str:
        return None
    cleaned = re.sub(r"[,$\s]", "", str(wage_str))
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def download_uscis_data(year: int, data_dir: str = "data/intel") -> Path:
    url = USCIS_DATA_URLS.get(year)
    if not url:
        raise ValueError(f"No USCIS data URL for year {year}")

    dest_dir = Path(data_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    filename = url.split("/")[-1]
    dest = dest_dir / filename

    if dest.exists():
        logger.info("uscis_data_cached", year=year, path=str(dest))
        return dest

    logger.info("downloading_uscis_data", year=year, url=url)
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        dest.write_bytes(response.content)

    logger.info("uscis_data_downloaded", year=year, size=dest.stat().st_size)
    return dest


def parse_uscis_csv(csv_path: Path, year: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    source_file = csv_path.name

    content: str
    if csv_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(csv_path) as zf:
            csv_name = next(n for n in zf.namelist() if n.endswith(".csv"))
            content = zf.read(csv_name).decode("utf-8", errors="replace")
    else:
        content = csv_path.read_text(encoding="utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        record = _parse_uscis_row(row, year, source_file)
        if record is not None:
            records.append(record)

    logger.info("uscis_csv_parsed", year=year, records=len(records))
    return records


def _parse_uscis_row(
    row: dict[str, str], year: int, source_file: str
) -> dict[str, Any] | None:
    try:
        employer = (row.get("Employer") or "").strip()

        if not employer:
            return None

        initial_approval = int(row.get("Initial Approval") or 0)
        initial_denial = int(row.get("Initial Denial") or 0)
        continuing_approval = int(row.get("Continuing Approval") or 0)
        continuing_denial = int(row.get("Continuing Denial") or 0)

        total_approved = initial_approval + continuing_approval
        total_denied = initial_denial + continuing_denial
        total = total_approved + total_denied

        if total == 0:
            return None

        state = (row.get("State") or "").strip()
        city = (row.get("City") or "").strip()

        case_status = "Certified" if total_approved > 0 else "Denied"

        return {
            "employer_name": employer,
            "employer_name_normalized": normalize_company(employer),
            "job_title": "H1B Employee",
            "job_title_normalized": "h1b employee",
            "wage_from": None,
            "wage_to": None,
            "wage_unit": "Year",
            "case_status": case_status,
            "year": year,
            "worksite_state": state,
            "worksite_city": city,
            "is_ml_role": False,
            "source_file": source_file,
            # petition counts — stripped before ORM insert
            "total_approved": total_approved,
            "total_denied": total_denied,
        }
    except Exception:
        return None
