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
    2021: "https://www.uscis.gov/sites/default/files/document/data/h1b_datahubexport-2021.csv",
}

USCIS_URL_PATTERNS: list[str] = [
    "https://www.uscis.gov/sites/default/files/document/data/h1b_datahubexport-{year}.csv",
    "https://www.uscis.gov/sites/default/files/document/data/H-1B_Disclosure_Data_FY{year}_Q4.csv",
]

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


def download_uscis_data(
    year: int,
    data_dir: str = "data/intel",
) -> Path | None:
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    output_path = Path(data_dir) / f"h1b_{year}.csv"

    if output_path.exists():
        logger.info("h1b_data_cached", year=year)
        return output_path

    urls_to_try: list[str] = []
    if year in USCIS_DATA_URLS:
        urls_to_try.append(USCIS_DATA_URLS[year])
    for pattern in USCIS_URL_PATTERNS:
        url = pattern.format(year=year)
        if url not in urls_to_try:
            urls_to_try.append(url)

    for url in urls_to_try:
        logger.info("trying_uscis_url", year=year, url=url)
        try:
            with httpx.stream("GET", url, timeout=60, follow_redirects=True) as r:
                if r.status_code == 404:
                    continue
                r.raise_for_status()
                with open(output_path, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=8192):
                        f.write(chunk)
            size = output_path.stat().st_size
            logger.info("uscis_data_downloaded", year=year, size=size)
            return output_path
        except Exception as e:
            logger.debug("uscis_url_failed", url=url, error=str(e))
            if output_path.exists():
                output_path.unlink()
            continue

    logger.warning("h1b_data_unavailable", year=year)
    return None


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


def _parse_uscis_row(row: dict[str, str], year: int, source_file: str) -> dict[str, Any] | None:
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
