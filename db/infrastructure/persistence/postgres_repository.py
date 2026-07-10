"""
Postgres/Supabase implementation of CaseRepository, using the SQLAlchemy
models already defined in db/models.py. This is what Stage 2 (FastAPI)
uses while developing against Supabase.
"""
from typing import Any

from sqlalchemy import func

from db.connection import get_session
from db.models import (
    CaseMaster, District, CrimeSubHead, CrimeHead, CaseCategory,
    GravityOffence, CaseStatusMaster, Victim, Accused, ArrestSurrender,
)
from domain.interfaces.case_repository import CaseRepository


class PostgresCaseRepository(CaseRepository):

    def get_total_case_count(self) -> int:
        session = get_session()
        try:
            return session.query(func.count(CaseMaster.CaseMasterID)).scalar() or 0
        finally:
            session.close()

    def get_accused_list(self, limit: int = 50) -> list[dict[str, Any]]:
        session = get_session()
        try:
            rows = (
                session.query(
                    Accused.AccusedName, Accused.AgeYear, Accused.GenderID,
                    CaseMaster.CrimeNo, CrimeSubHead.CrimeHeadName,
                    CaseStatusMaster.CaseStatusName,
                )
                .join(CaseMaster, Accused.CaseMasterID == CaseMaster.CaseMasterID)
                .join(CrimeSubHead, CaseMaster.CrimeMinorHeadID == CrimeSubHead.CrimeSubHeadID)
                .join(CaseStatusMaster, CaseMaster.CaseStatusID == CaseStatusMaster.CaseStatusID)
                .order_by(CaseMaster.CrimeRegisteredDate.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "accused_name": r[0], "age": r[1], "gender": r[2],
                    "crime_no": r[3], "crime_type": r[4], "case_status": r[5],
                }
                for r in rows
            ]
        finally:
            session.close()

    def get_case_by_id(self, case_id: int) -> dict[str, Any] | None:
        session = get_session()
        try:
            row = (
                session.query(
                    CaseMaster.CaseMasterID, CaseMaster.CrimeNo, CaseMaster.CrimeRegisteredDate,
                    District.DistrictName, CrimeSubHead.CrimeHeadName, CaseCategory.LookupValue,
                    GravityOffence.LookupValue, CaseStatusMaster.CaseStatusName,
                    CaseMaster.latitude, CaseMaster.longitude, CaseMaster.BriefFacts,
                )
                .join(District, CaseMaster.DistrictID == District.DistrictID)
                .join(CrimeSubHead, CaseMaster.CrimeMinorHeadID == CrimeSubHead.CrimeSubHeadID)
                .join(CaseCategory, CaseMaster.CaseCategoryID == CaseCategory.CaseCategoryID)
                .join(GravityOffence, CaseMaster.GravityOffenceID == GravityOffence.GravityOffenceID)
                .join(CaseStatusMaster, CaseMaster.CaseStatusID == CaseStatusMaster.CaseStatusID)
                .filter(CaseMaster.CaseMasterID == case_id)
                .first()
            )
            if not row:
                return None
            return {
                "case_id": row[0], "crime_no": row[1], "date": str(row[2]),
                "district": row[3], "crime_type": row[4], "category": row[5],
                "gravity": row[6], "status": row[7],
                "lat": float(row[8]) if row[8] else None,
                "lng": float(row[9]) if row[9] else None,
                "brief": row[10],
            }
        finally:
            session.close()

    def get_district_counts(self) -> list[dict[str, Any]]:
        session = get_session()
        try:
            rows = (
                session.query(District.DistrictName, func.count(CaseMaster.CaseMasterID))
                .join(CaseMaster, CaseMaster.DistrictID == District.DistrictID)
                .group_by(District.DistrictName)
                .order_by(func.count(CaseMaster.CaseMasterID).desc())
                .all()
            )
            return [{"district": r[0], "count": r[1]} for r in rows]
        finally:
            session.close()

    def get_crime_type_counts(self, district: str | None = None) -> list[dict[str, Any]]:
        session = get_session()
        try:
            q = (
                session.query(CrimeSubHead.CrimeHeadName, func.count(CaseMaster.CaseMasterID))
                .join(CaseMaster, CaseMaster.CrimeMinorHeadID == CrimeSubHead.CrimeSubHeadID)
            )
            if district:
                q = q.join(District, CaseMaster.DistrictID == District.DistrictID).filter(
                    District.DistrictName == district
                )
            rows = q.group_by(CrimeSubHead.CrimeHeadName).order_by(
                func.count(CaseMaster.CaseMasterID).desc()
            ).all()
            return [{"crime_type": r[0], "count": r[1]} for r in rows]
        finally:
            session.close()

    def get_monthly_trend(self, district: str | None = None) -> list[dict[str, Any]]:
        session = get_session()
        try:
            month_expr = func.to_char(CaseMaster.CrimeRegisteredDate, "YYYY-MM")
            q = session.query(month_expr, func.count(CaseMaster.CaseMasterID))
            if district:
                q = q.join(District, CaseMaster.DistrictID == District.DistrictID).filter(
                    District.DistrictName == district
                )
            rows = q.group_by(month_expr).order_by(month_expr).all()
            return [{"month": r[0], "count": r[1]} for r in rows]
        finally:
            session.close()

    def get_cases_for_map(self, limit: int = 5000) -> list[dict[str, Any]]:
        session = get_session()
        try:
            rows = (
                session.query(
                    CaseMaster.latitude, CaseMaster.longitude,
                    CrimeSubHead.CrimeHeadName, CaseMaster.CrimeRegisteredDate,
                )
                .join(CrimeSubHead, CaseMaster.CrimeMinorHeadID == CrimeSubHead.CrimeSubHeadID)
                .filter(CaseMaster.latitude.isnot(None))
                .limit(limit)
                .all()
            )
            return [
                {"lat": float(r[0]), "lng": float(r[1]), "crime_type": r[2], "date": str(r[3])}
                for r in rows
            ]
        finally:
            session.close()

    def get_case_network(self, case_id: int) -> dict[str, Any]:
        session = get_session()
        try:
            victims = session.query(Victim).filter_by(CaseMasterID=case_id).all()
            accused = session.query(Accused).filter_by(CaseMasterID=case_id).all()
            arrests = session.query(ArrestSurrender).filter_by(CaseMasterID=case_id).all()

            nodes = [{"id": f"case_{case_id}", "label": f"Case {case_id}", "type": "case"}]
            edges = []
            for v in victims:
                nodes.append({"id": f"victim_{v.VictimMasterID}", "label": v.VictimName, "type": "victim"})
                edges.append({"source": f"case_{case_id}", "target": f"victim_{v.VictimMasterID}"})
            for a in accused:
                nodes.append({"id": f"accused_{a.AccusedMasterID}", "label": a.AccusedName, "type": "accused"})
                edges.append({"source": f"case_{case_id}", "target": f"accused_{a.AccusedMasterID}"})
            for ar in arrests:
                # One arrest EVENT can cover multiple accused (joint
                # raids), so walk the junction table rather than
                # assuming a single accused per event.
                nodes.append({
                    "id": f"arrest_{ar.ArrestSurrenderID}",
                    "label": f"Arrest {ar.ArrestSurrenderDate}",
                    "type": "arrest_event",
                })
                for link in ar.accused_links:
                    edges.append({
                        "source": f"accused_{link.AccusedMasterID}",
                        "target": f"arrest_{ar.ArrestSurrenderID}",
                        "label": "primary" if link.IsAccused else "co-arrested",
                    })
                edges.append({
                    "source": f"arrest_{ar.ArrestSurrenderID}",
                    "target": f"case_{case_id}",
                    "label": "arrest event for",
                })
            return {"nodes": nodes, "edges": edges}
        finally:
            session.close()

    def insert_case(self, case_data: dict[str, Any]) -> int:
        session = get_session()
        try:
            case = CaseMaster(**case_data)
            session.add(case)
            session.commit()
            session.refresh(case)
            return case.CaseMasterID
        finally:
            session.close()
