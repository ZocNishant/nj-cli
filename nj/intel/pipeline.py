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
    2022: "https://www.uscis.gov/sites/default/files/document/data/H-1B_Disclosure_Data_FY2022_Q4.csv",
    2023: "https://www.uscis.gov/sites/default/files/document/data/H-1B_Disclosure_Data_FY2023_Q4.csv",
    2024: "https://www.uscis.gov/sites/default/files/document/data/H-1B_Disclosure_Data_FY2024_Q4.csv",
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
    employer = (
        row.get("EMPLOYER_NAME")
        or row.get("PETITIONER_NAME")
        or row.get("employer_name")
        or ""
    ).strip()
    if not employer:
        return None

    title = (
        row.get("JOB_TITLE")
        or row.get("SOC_TITLE")
        or row.get("job_title")
        or ""
    ).strip()

    status = (
        row.get("CASE_STATUS")
        or row.get("case_status")
        or ""
    ).strip()

    wage_from_raw = (
        row.get("WAGE_RATE_OF_PAY_FROM")
        or row.get("PREVAILING_WAGE")
        or row.get("wage_from")
        or None
    )
    wage_to_raw = row.get("WAGE_RATE_OF_PAY_TO") or row.get("wage_to") or None
    wage_unit_raw = (
        row.get("WAGE_UNIT_OF_PAY")
        or row.get("wage_unit")
        or "Year"
    ).strip()

    wage_from = parse_wage(wage_from_raw)
    wage_to = parse_wage(wage_to_raw)

    # Annualize hourly wages
    unit_lower = wage_unit_raw.lower()
    if unit_lower in ("hour", "hr", "hourly"):
        if wage_from is not None:
            wage_from = wage_from * 2080
        if wage_to is not None:
            wage_to = wage_to * 2080
        wage_unit = "year"
    elif unit_lower in ("week", "weekly"):
        if wage_from is not None:
            wage_from = wage_from * 52
        if wage_to is not None:
            wage_to = wage_to * 52
        wage_unit = "year"
    elif unit_lower in ("month", "monthly", "bi-weekly"):
        if wage_from is not None:
            wage_from = wage_from * 12
        if wage_to is not None:
            wage_to = wage_to * 12
        wage_unit = "year"
    else:
        wage_unit = "year"

    state = (
        row.get("WORKSITE_STATE")
        or row.get("EMPLOYER_STATE")
        or row.get("worksite_state")
        or ""
    ).strip().upper()
    city = (
        row.get("WORKSITE_CITY")
        or row.get("EMPLOYER_CITY")
        or row.get("worksite_city")
        or ""
    ).strip().title()

    return {
        "employer_name": employer,
        "employer_name_normalized": normalize_company(employer),
        "job_title": title,
        "job_title_normalized": normalize_title(title),
        "wage_from": wage_from,
        "wage_to": wage_to,
        "wage_unit": wage_unit,
        "case_status": status,
        "year": year,
        "worksite_state": state,
        "worksite_city": city,
        "is_ml_role": is_ml_role(title),
        "source_file": source_file,
    }
