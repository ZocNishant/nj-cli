from __future__ import annotations

import statistics
from collections import Counter
from datetime import datetime, UTC
from typing import Any

from sqlalchemy import func, select, text

from nj.db.engine import get_session
from nj.db.models import CompanyIntelORM, H1BPetitionORM
from nj.utils.logger import get_logger

logger = get_logger(__name__)


def _compute_sponsor_tier(
    total: int, approval_rate: float, ml_count: int
) -> str:
    if total >= 100 and approval_rate >= 0.85 and ml_count >= 10:
        return "STRONG"
    if total >= 20 and approval_rate >= 0.70:
        return "MODERATE"
    if total >= 5:
        return "WEAK"
    return "UNKNOWN"


class IntelRepo:
    def __init__(self, db_path: str = "data/nj.db") -> None:
        self._db_path = db_path

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def bulk_insert_petitions(
        self, records: list[dict[str, Any]], batch_size: int = 1000
    ) -> int:
        inserted = 0
        with get_session(self._db_path) as session:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                for rec in batch:
                    orm = H1BPetitionORM(**rec)
                    session.add(orm)
                session.flush()
                inserted += len(batch)
        logger.info("petitions_inserted", count=inserted)
        return inserted

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def petitions_exist_for_year(self, year: int) -> bool:
        with get_session(self._db_path) as session:
            count = (
                session.execute(
                    select(func.count()).select_from(H1BPetitionORM).where(
                        H1BPetitionORM.year == year
                    )
                ).scalar()
                or 0
            )
            return count > 0

    def search_company(
        self, query: str, ml_only: bool = False
    ) -> list[dict[str, Any]]:
        pattern = f"%{query.lower()}%"
        with get_session(self._db_path) as session:
            stmt = select(CompanyIntelORM).where(
                CompanyIntelORM.name_normalized.like(pattern)
            )
            if ml_only:
                stmt = stmt.where(CompanyIntelORM.ml_ai_petitions > 0)
            stmt = stmt.order_by(CompanyIntelORM.total_petitions.desc()).limit(20)
            rows = session.execute(stmt).scalars().all()
            return [_company_to_dict(r) for r in rows]

    def get_company_profile(self, company_name: str) -> dict[str, Any] | None:
        from nj.intel.pipeline import normalize_company

        norm = normalize_company(company_name)
        with get_session(self._db_path) as session:
            # Try exact normalized match first, then partial
            row = session.execute(
                select(CompanyIntelORM).where(
                    CompanyIntelORM.name_normalized == norm
                )
            ).scalar_one_or_none()

            if row is None:
                row = session.execute(
                    select(CompanyIntelORM)
                    .where(CompanyIntelORM.name_normalized.like(f"%{norm}%"))
                    .order_by(CompanyIntelORM.total_petitions.desc())
                    .limit(1)
                ).scalar_one_or_none()

            if row is None:
                return None

            return _company_to_dict(row)

    def get_top_ml_sponsors(
        self, state: str = "", year: int = 0, limit: int = 20
    ) -> list[dict[str, Any]]:
        with get_session(self._db_path) as session:
            stmt = (
                select(CompanyIntelORM)
                .where(CompanyIntelORM.ml_ai_petitions > 0)
                .order_by(CompanyIntelORM.ml_ai_petitions.desc())
                .limit(limit)
            )
            rows = session.execute(stmt).scalars().all()
            results = [_company_to_dict(r) for r in rows]

        if state:
            state_upper = state.upper()
            # Re-filter by state using petition-level data
            with get_session(self._db_path) as session:
                stmt2 = (
                    select(
                        H1BPetitionORM.employer_name_normalized,
                        func.count().label("cnt"),
                    )
                    .where(
                        H1BPetitionORM.is_ml_role == True,  # noqa: E712
                        H1BPetitionORM.worksite_state == state_upper,
                    )
                    .group_by(H1BPetitionORM.employer_name_normalized)
                    .order_by(text("cnt DESC"))
                    .limit(limit)
                )
                if year:
                    stmt2 = stmt2.where(H1BPetitionORM.year == year)
                rows2 = session.execute(stmt2).all()
                norm_names = {r.employer_name_normalized for r in rows2}

            results = [r for r in results if r["name_normalized"] in norm_names]

        return results[:limit]

    def get_role_sponsorship(
        self, role_query: str, limit: int = 15
    ) -> list[dict[str, Any]]:
        pattern = f"%{role_query.lower()}%"
        with get_session(self._db_path) as session:
            stmt = (
                select(
                    H1BPetitionORM.employer_name,
                    H1BPetitionORM.employer_name_normalized,
                    func.count().label("petitions"),
                    func.avg(H1BPetitionORM.wage_from).label("avg_wage"),
                )
                .where(H1BPetitionORM.job_title_normalized.like(pattern))
                .group_by(
                    H1BPetitionORM.employer_name,
                    H1BPetitionORM.employer_name_normalized,
                )
                .order_by(text("petitions DESC"))
                .limit(limit)
            )
            rows = session.execute(stmt).all()
            return [
                {
                    "employer": r.employer_name,
                    "petitions": r.petitions,
                    "avg_salary": round(r.avg_wage or 0),
                }
                for r in rows
            ]

    def get_stats(self) -> dict[str, Any]:
        with get_session(self._db_path) as session:
            total = (
                session.execute(
                    select(func.count()).select_from(H1BPetitionORM)
                ).scalar()
                or 0
            )
            ml = (
                session.execute(
                    select(func.count())
                    .select_from(H1BPetitionORM)
                    .where(H1BPetitionORM.is_ml_role == True)  # noqa: E712
                ).scalar()
                or 0
            )
            years_rows = session.execute(
                select(H1BPetitionORM.year).distinct()
            ).scalars().all()
            years = sorted(years_rows)
        return {"total_petitions": total, "ml_petitions": ml, "years": years}

    # ------------------------------------------------------------------
    # Aggregation (called after bulk insert to build company_intel)
    # ------------------------------------------------------------------

    def rebuild_company_intel(self) -> int:
        logger.info("rebuilding_company_intel")
        with get_session(self._db_path) as session:
            # Clear existing
            session.execute(text("DELETE FROM company_intel"))
            session.flush()

            # Aggregate from petitions
            stmt = (
                select(
                    H1BPetitionORM.employer_name,
                    H1BPetitionORM.employer_name_normalized,
                    func.count().label("total"),
                    func.sum(
                        (H1BPetitionORM.case_status.ilike("%certif%")).cast(
                            type_=H1BPetitionORM.__table__.c.id.type.__class__()
                        )
                    ).label("approved"),
                    func.sum(
                        H1BPetitionORM.is_ml_role.cast(
                            type_=H1BPetitionORM.__table__.c.id.type.__class__()
                        )
                    ).label("ml_count"),
                    func.avg(H1BPetitionORM.wage_from).label("avg_sal"),
                )
                .group_by(
                    H1BPetitionORM.employer_name,
                    H1BPetitionORM.employer_name_normalized,
                )
            )
            rows = session.execute(stmt).all()

        inserted = 0
        with get_session(self._db_path) as session:
            for r in rows:
                total = r.total or 0
                approved = int(r.approved or 0)
                ml_count = int(r.ml_count or 0)
                avg_sal = float(r.avg_sal) if r.avg_sal else None
                approval_rate = approved / total if total > 0 else 0.0
                tier = _compute_sponsor_tier(total, approval_rate, ml_count)

                # Get years active and states
                with get_session(self._db_path) as sub:
                    years_rows = sub.execute(
                        select(H1BPetitionORM.year)
                        .where(
                            H1BPetitionORM.employer_name_normalized
                            == r.employer_name_normalized
                        )
                        .distinct()
                    ).scalars().all()
                    states_rows = sub.execute(
                        select(H1BPetitionORM.worksite_state)
                        .where(
                            H1BPetitionORM.employer_name_normalized
                            == r.employer_name_normalized,
                            H1BPetitionORM.worksite_state != "",
                        )
                        .distinct()
                        .limit(10)
                    ).scalars().all()
                    top_role_rows = sub.execute(
                        select(
                            H1BPetitionORM.job_title,
                            func.count().label("cnt"),
                        )
                        .where(
                            H1BPetitionORM.employer_name_normalized
                            == r.employer_name_normalized
                        )
                        .group_by(H1BPetitionORM.job_title)
                        .order_by(text("cnt DESC"))
                        .limit(5)
                    ).all()

                orm = CompanyIntelORM(
                    name=r.employer_name,
                    name_normalized=r.employer_name_normalized,
                    total_petitions=total,
                    approved_petitions=approved,
                    denied_petitions=total - approved,
                    ml_ai_petitions=ml_count,
                    median_salary=avg_sal,
                    avg_salary=avg_sal,
                    approval_rate=approval_rate,
                    sponsor_tier=tier,
                    last_updated=datetime.now(UTC),
                    years_active=sorted(years_rows),
                    top_roles=[tr.job_title for tr in top_role_rows],
                    states=list(states_rows),
                )
                session.add(orm)
                inserted += 1

        logger.info("company_intel_rebuilt", companies=inserted)
        return inserted


def _petition_to_dict(r: H1BPetitionORM) -> dict[str, Any]:
    return {
        "id": r.id,
        "employer_name": r.employer_name,
        "employer_name_normalized": r.employer_name_normalized,
        "job_title": r.job_title,
        "wage_from": r.wage_from,
        "wage_to": r.wage_to,
        "wage_unit": r.wage_unit,
        "case_status": r.case_status,
        "year": r.year,
        "worksite_state": r.worksite_state,
        "worksite_city": r.worksite_city,
        "is_ml_role": r.is_ml_role,
    }


def _company_to_dict(r: CompanyIntelORM) -> dict[str, Any]:
    return {
        "name": r.name,
        "name_normalized": r.name_normalized,
        "total_petitions": r.total_petitions,
        "approved_petitions": r.approved_petitions,
        "denied_petitions": r.denied_petitions,
        "ml_ai_petitions": r.ml_ai_petitions,
        "median_salary": r.median_salary,
        "avg_salary": r.avg_salary,
        "approval_rate": r.approval_rate,
        "sponsor_tier": r.sponsor_tier,
        "years_active": r.years_active or [],
        "top_roles": r.top_roles or [],
        "states": r.states or [],
    }
