from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text

from nj.db.engine import get_session
from nj.db.models import CompanyIntelORM, H1BPetitionORM
from nj.utils.logger import get_logger

logger = get_logger(__name__)


def _compute_sponsor_tier(total: int, approval_rate: float, ml_count: int) -> str:
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

    _ORM_FIELDS = frozenset(
        {
            "employer_name",
            "employer_name_normalized",
            "job_title",
            "job_title_normalized",
            "wage_from",
            "wage_to",
            "wage_unit",
            "case_status",
            "year",
            "worksite_state",
            "worksite_city",
            "is_ml_role",
            "source_file",
        }
    )

    def bulk_insert_petitions(self, records: list[dict[str, Any]], batch_size: int = 1000) -> int:
        inserted = 0
        with get_session(self._db_path) as session:
            for i in range(0, len(records), batch_size):
                batch = records[i : i + batch_size]
                for rec in batch:
                    orm_rec = {k: v for k, v in rec.items() if k in self._ORM_FIELDS}
                    orm = H1BPetitionORM(**orm_rec)
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
                    select(func.count())
                    .select_from(H1BPetitionORM)
                    .where(H1BPetitionORM.year == year)
                ).scalar()
                or 0
            )
            return count > 0

    def search_company(self, query: str, ml_only: bool = False) -> list[dict[str, Any]]:
        pattern = f"%{query.lower()}%"
        with get_session(self._db_path) as session:
            stmt = select(CompanyIntelORM).where(CompanyIntelORM.name_normalized.like(pattern))
            if ml_only:
                stmt = stmt.where(CompanyIntelORM.ml_ai_petitions > 0)
            stmt = stmt.order_by(CompanyIntelORM.total_petitions.desc()).limit(20)
            rows = session.execute(stmt).scalars().all()
            return [_company_to_dict(r) for r in rows]

    def get_company_profile(self, company_name: str) -> dict[str, Any] | None:
        normalized = company_name.lower().strip()[:20]
        with get_session(self._db_path) as session:
            rows = (
                session.execute(
                    select(H1BPetitionORM).where(
                        H1BPetitionORM.employer_name_normalized.contains(normalized)
                    )
                )
                .scalars()
                .all()
            )

            if not rows:
                return {}

            # Aggregate across years
            total_approved = 0
            total_denied = 0
            years: set[int] = set()
            states: list[str] = []

            for r in rows:
                if "certif" in r.case_status.lower():
                    total_approved += 1
                else:
                    total_denied += 1
                years.add(r.year)
                if r.worksite_state:
                    states.append(r.worksite_state)

            total = total_approved + total_denied
            approval_rate = total_approved / total * 100 if total > 0 else 0.0
            sponsor_tier = _compute_sponsor_tier(total, approval_rate, 0)

            from collections import Counter

            state_counts = Counter(states)
            top_states = [s for s, _ in state_counts.most_common(5)]

            return {
                "company": rows[0].employer_name,
                "total_petitions": total,
                "approved": total_approved,
                "denied": total_denied,
                "approval_rate": round(approval_rate, 1),
                "ml_ai_petitions": 0,
                "median_salary": None,
                "sponsor_tier": sponsor_tier,
                "top_roles": [],
                "years_active": sorted(years),
                "top_states": top_states,
            }

    def get_top_ml_sponsors(
        self,
        state: str | None = None,
        year: int | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        with get_session(self._db_path) as session:
            stmt = select(
                H1BPetitionORM.employer_name,
                func.count(H1BPetitionORM.id).label("total"),
            ).where(H1BPetitionORM.case_status.contains("Certif"))
            if state:
                stmt = stmt.where(H1BPetitionORM.worksite_state == state.upper())
            if year:
                stmt = stmt.where(H1BPetitionORM.year == year)
            stmt = (
                stmt.group_by(H1BPetitionORM.employer_name)
                .order_by(text("total DESC"))
                .limit(limit)
            )
            results = session.execute(stmt).all()

            return [
                {
                    "company": r.employer_name,
                    "total_ml_petitions": r.total,
                    "avg_salary": None,
                    "sponsor_tier": _compute_sponsor_tier(r.total, 80, 0),
                }
                for r in results
            ]

    def get_role_sponsorship(self, role_query: str, limit: int = 15) -> list[dict[str, Any]]:
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
            total = session.execute(select(func.count()).select_from(H1BPetitionORM)).scalar() or 0
            ml = (
                session.execute(
                    select(func.count())
                    .select_from(H1BPetitionORM)
                    .where(H1BPetitionORM.is_ml_role == True)  # noqa: E712
                ).scalar()
                or 0
            )
            years_rows = session.execute(select(H1BPetitionORM.year).distinct()).scalars().all()
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
            stmt = select(
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
            ).group_by(
                H1BPetitionORM.employer_name,
                H1BPetitionORM.employer_name_normalized,
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
                    years_rows = (
                        sub.execute(
                            select(H1BPetitionORM.year)
                            .where(
                                H1BPetitionORM.employer_name_normalized
                                == r.employer_name_normalized
                            )
                            .distinct()
                        )
                        .scalars()
                        .all()
                    )
                    states_rows = (
                        sub.execute(
                            select(H1BPetitionORM.worksite_state)
                            .where(
                                H1BPetitionORM.employer_name_normalized
                                == r.employer_name_normalized,
                                H1BPetitionORM.worksite_state != "",
                            )
                            .distinct()
                            .limit(10)
                        )
                        .scalars()
                        .all()
                    )
                    top_role_rows = sub.execute(
                        select(
                            H1BPetitionORM.job_title,
                            func.count().label("cnt"),
                        )
                        .where(
                            H1BPetitionORM.employer_name_normalized == r.employer_name_normalized
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
