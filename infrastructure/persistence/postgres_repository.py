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
    CasteMaster, ReligionMaster, OccupationMaster, ComplainantDetails,
    ChargesheetDetails,
)
from domain.interfaces.case_repository import CaseRepository


def _risk_tier(case_count: int) -> str:
    """v1 risk scoring -- PRD's own words: 'no ML needed for a
    defensible v1', a simple count-based tier. Thresholds are a
    starting point, not derived from any real distribution; revisit
    once real dataset volume/repeat-offender rates are known."""
    if case_count >= 5:
        return "high"
    if case_count >= 3:
        return "medium"
    return "low"


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

    def get_monthly_trend(
        self, district: str | None = None, crime_type: str | None = None
    ) -> list[dict[str, Any]]:
        session = get_session()
        try:
            month_expr = func.to_char(CaseMaster.CrimeRegisteredDate, "YYYY-MM")
            q = session.query(month_expr, func.count(CaseMaster.CaseMasterID))
            if district:
                q = q.join(District, CaseMaster.DistrictID == District.DistrictID).filter(
                    District.DistrictName == district
                )
            if crime_type:
                q = q.join(
                    CrimeSubHead, CaseMaster.CrimeMinorHeadID == CrimeSubHead.CrimeSubHeadID
                ).filter(CrimeSubHead.CrimeHeadName == crime_type)
            rows = q.group_by(month_expr).order_by(month_expr).all()
            return [{"month": r[0], "count": r[1]} for r in rows]
        finally:
            session.close()

    def get_cases_for_map(
        self, limit: int = 5000, crime_type: str | None = None
    ) -> list[dict[str, Any]]:
        session = get_session()
        try:
            q = (
                session.query(
                    CaseMaster.CaseMasterID, CaseMaster.latitude, CaseMaster.longitude,
                    CrimeSubHead.CrimeHeadName, CaseMaster.CrimeRegisteredDate,
                )
                .join(CrimeSubHead, CaseMaster.CrimeMinorHeadID == CrimeSubHead.CrimeSubHeadID)
                .filter(CaseMaster.latitude.isnot(None))
            )
            if crime_type:
                q = q.filter(CrimeSubHead.CrimeHeadName == crime_type)
            rows = q.limit(limit).all()
            return [
                {
                    "case_id": r[0], "lat": float(r[1]), "lng": float(r[2]),
                    "crime_type": r[3], "date": str(r[4]),
                }
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

            # Cross-case flag: does this accused's (normalized) name appear
            # in 2+ distinct cases overall -- same name-matching basis as
            # get_repeat_offender_network(), scoped to just the names
            # present in THIS case so it's one cheap extra query, not a
            # full-table scan repeated per node.
            accused_names = [a.AccusedName for a in accused]
            cross_case_counts: dict[str, int] = {}
            if accused_names:
                norm_name = func.lower(func.trim(Accused.AccusedName))
                norm_targets = [n.strip().lower() for n in accused_names]
                rows = (
                    session.query(norm_name, func.count(func.distinct(Accused.CaseMasterID)))
                    .filter(norm_name.in_(norm_targets))
                    .group_by(norm_name)
                    .all()
                )
                cross_case_counts = {name: count for name, count in rows}

            nodes = [{"id": f"case_{case_id}", "label": f"Case {case_id}", "type": "case"}]
            edges = []
            for v in victims:
                nodes.append({
                    "id": f"victim_{v.VictimMasterID}", "label": v.VictimName, "type": "victim",
                    "age": v.AgeYear, "gender": v.GenderID,
                })
                edges.append({"source": f"case_{case_id}", "target": f"victim_{v.VictimMasterID}"})
            for a in accused:
                case_count = cross_case_counts.get(a.AccusedName.strip().lower(), 1)
                nodes.append({
                    "id": f"accused_{a.AccusedMasterID}", "label": a.AccusedName, "type": "accused",
                    "age": a.AgeYear, "gender": a.GenderID,
                    "cross_case": case_count >= 2,
                    "case_count": case_count,
                })
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

    def get_case_timeline(self, case_id: int) -> list[dict[str, Any]]:
        session = get_session()
        try:
            case = session.query(
                CaseMaster.CrimeRegisteredDate, CaseMaster.IncidentFromDate,
                CaseMaster.IncidentToDate, CaseMaster.InfoReceivedPSDate,
            ).filter(CaseMaster.CaseMasterID == case_id).first()
            if not case:
                return []

            events: list[dict[str, Any]] = []
            if case[0]:
                events.append({"date": str(case[0]), "label": "Case registered", "type": "registered"})
            if case[1]:
                events.append({"date": str(case[1]), "label": "Incident start", "type": "incident_start"})
            if case[2]:
                events.append({"date": str(case[2]), "label": "Incident end", "type": "incident_end"})
            if case[3]:
                events.append({"date": str(case[3]), "label": "Info received at police station", "type": "info_received"})

            arrests = (
                session.query(ArrestSurrender.ArrestSurrenderDate)
                .filter(ArrestSurrender.CaseMasterID == case_id)
                .all()
            )
            for (arrest_date,) in arrests:
                if arrest_date:
                    events.append({"date": str(arrest_date), "label": "Arrest/surrender", "type": "arrest"})

            # ChargesheetDetails isn't seeded in the current dataset (per
            # the project README) -- this must return [] gracefully here,
            # not assume at least one row exists.
            chargesheets = (
                session.query(ChargesheetDetails.csdate, ChargesheetDetails.cstype)
                .filter(ChargesheetDetails.CaseMasterID == case_id)
                .all()
            )
            for cs_date, cs_type in chargesheets:
                if cs_date:
                    label = {"A": "Chargesheet filed", "B": "Marked false case", "C": "Marked undetected"}.get(
                        cs_type, "Chargesheet event"
                    )
                    events.append({"date": str(cs_date), "label": label, "type": "chargesheet"})

            events.sort(key=lambda e: e["date"])
            return events
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

    def get_cross_case_links(self, accused_name: str) -> dict[str, Any]:
        session = get_session()
        try:
            norm = accused_name.strip().lower()
            rows = (
                session.query(
                    Accused.AccusedName, CaseMaster.CaseMasterID, CaseMaster.CrimeNo,
                    District.DistrictName, CrimeSubHead.CrimeHeadName,
                    CaseMaster.CrimeRegisteredDate,
                )
                .join(CaseMaster, Accused.CaseMasterID == CaseMaster.CaseMasterID)
                .join(District, CaseMaster.DistrictID == District.DistrictID)
                .join(CrimeSubHead, CaseMaster.CrimeMinorHeadID == CrimeSubHead.CrimeSubHeadID)
                .filter(func.lower(func.trim(Accused.AccusedName)) == norm)
                .order_by(CaseMaster.CrimeRegisteredDate.desc())
                .all()
            )
            if not rows:
                return {
                    "accused_name": accused_name, "cases": [],
                    "match_count": 0, "match_basis": "name",
                }
            cases = [
                {
                    "case_id": r[1], "crime_no": r[2], "district": r[3],
                    "crime_type": r[4], "date": str(r[5]),
                }
                for r in rows
            ]
            return {
                "accused_name": rows[0][0], "cases": cases,
                "match_count": len(cases), "match_basis": "name",
            }
        finally:
            session.close()

    def get_repeat_offender_network(self, min_case_count: int = 2) -> list[dict[str, Any]]:
        session = get_session()
        try:
            norm_name = func.lower(func.trim(Accused.AccusedName))
            counts = (
                session.query(
                    norm_name.label("norm"),
                    func.count(func.distinct(Accused.CaseMasterID)).label("cnt"),
                )
                .group_by(norm_name)
                .having(func.count(func.distinct(Accused.CaseMasterID)) >= min_case_count)
                .subquery()
            )
            rows = (
                session.query(
                    Accused.AccusedName, CaseMaster.CaseMasterID, CaseMaster.CrimeNo,
                    District.DistrictName, CrimeSubHead.CrimeHeadName,
                    CaseMaster.CrimeRegisteredDate, counts.c.cnt,
                )
                .join(counts, func.lower(func.trim(Accused.AccusedName)) == counts.c.norm)
                .join(CaseMaster, Accused.CaseMasterID == CaseMaster.CaseMasterID)
                .join(District, CaseMaster.DistrictID == District.DistrictID)
                .join(CrimeSubHead, CaseMaster.CrimeMinorHeadID == CrimeSubHead.CrimeSubHeadID)
                .order_by(counts.c.cnt.desc(), Accused.AccusedName)
                .all()
            )
            grouped: dict[str, dict[str, Any]] = {}
            for name, case_id, crime_no, district, crime_type, date, cnt in rows:
                key = name.strip().lower()
                g = grouped.setdefault(
                    key, {"accused_name": name, "case_count": cnt, "cases": []}
                )
                g["cases"].append({
                    "case_id": case_id, "crime_no": crime_no, "district": district,
                    "crime_type": crime_type, "date": str(date),
                })
            result = list(grouped.values())
            for g in result:
                g["risk_tier"] = _risk_tier(g["case_count"])
            result.sort(key=lambda g: g["case_count"], reverse=True)
            return result
        finally:
            session.close()

    def get_investigative_leads(self, case_id: int) -> dict[str, Any]:
        session = get_session()
        try:
            case = (
                session.query(
                    CaseMaster.DistrictID, CaseMaster.CrimeMinorHeadID,
                )
                .filter(CaseMaster.CaseMasterID == case_id)
                .first()
            )
            if not case:
                return {"case_id": case_id, "cross_case_links": [], "similar_open_cases": []}
            district_id, crime_sub_head_id = case

            accused_names = [
                r[0] for r in
                session.query(Accused.AccusedName).filter(Accused.CaseMasterID == case_id).all()
            ]

            cross_case_links: list[dict[str, Any]] = []
            if accused_names:
                norm_name = func.lower(func.trim(Accused.AccusedName))
                norm_targets = [n.strip().lower() for n in accused_names]
                rows = (
                    session.query(
                        Accused.AccusedName, CaseMaster.CaseMasterID, CaseMaster.CrimeNo,
                        District.DistrictName, CrimeSubHead.CrimeHeadName,
                        CaseMaster.CrimeRegisteredDate,
                    )
                    .join(CaseMaster, Accused.CaseMasterID == CaseMaster.CaseMasterID)
                    .join(District, CaseMaster.DistrictID == District.DistrictID)
                    .join(CrimeSubHead, CaseMaster.CrimeMinorHeadID == CrimeSubHead.CrimeSubHeadID)
                    .filter(norm_name.in_(norm_targets))
                    .filter(CaseMaster.CaseMasterID != case_id)
                    .order_by(CaseMaster.CrimeRegisteredDate.desc())
                    .all()
                )
                cross_case_links = [
                    {
                        "accused_name": r[0], "case_id": r[1], "crime_no": r[2],
                        "district": r[3], "crime_type": r[4], "date": str(r[5]),
                    }
                    for r in rows
                ]

            open_statuses = ("Under Investigation", "Undetected")
            rows = (
                session.query(
                    CaseMaster.CaseMasterID, CaseMaster.CrimeNo, District.DistrictName,
                    CrimeSubHead.CrimeHeadName, CaseMaster.CrimeRegisteredDate,
                    CaseStatusMaster.CaseStatusName,
                )
                .join(District, CaseMaster.DistrictID == District.DistrictID)
                .join(CrimeSubHead, CaseMaster.CrimeMinorHeadID == CrimeSubHead.CrimeSubHeadID)
                .join(CaseStatusMaster, CaseMaster.CaseStatusID == CaseStatusMaster.CaseStatusID)
                .filter(CaseMaster.DistrictID == district_id)
                .filter(CaseMaster.CrimeMinorHeadID == crime_sub_head_id)
                .filter(CaseStatusMaster.CaseStatusName.in_(open_statuses))
                .filter(CaseMaster.CaseMasterID != case_id)
                .order_by(CaseMaster.CrimeRegisteredDate.desc())
                .limit(10)
                .all()
            )
            similar_open_cases = [
                {
                    "case_id": r[0], "crime_no": r[1], "district": r[2],
                    "crime_type": r[3], "date": str(r[4]), "status": r[5],
                }
                for r in rows
            ]

            return {
                "case_id": case_id,
                "cross_case_links": cross_case_links,
                "similar_open_cases": similar_open_cases,
            }
        finally:
            session.close()

    def get_sociological_breakdown(self, crime_type: str | None = None) -> list[dict[str, Any]]:
        session = get_session()
        try:
            q = (
                session.query(
                    CasteMaster.caste_master_name, ReligionMaster.ReligionName,
                    OccupationMaster.OccupationName, CrimeSubHead.CrimeHeadName,
                    func.count(ComplainantDetails.ComplainantID),
                )
                .select_from(ComplainantDetails)
                .join(CaseMaster, ComplainantDetails.CaseMasterID == CaseMaster.CaseMasterID)
                .join(CrimeSubHead, CaseMaster.CrimeMinorHeadID == CrimeSubHead.CrimeSubHeadID)
                .outerjoin(CasteMaster, ComplainantDetails.CasteID == CasteMaster.caste_master_id)
                .outerjoin(ReligionMaster, ComplainantDetails.ReligionID == ReligionMaster.ReligionID)
                .outerjoin(OccupationMaster, ComplainantDetails.OccupationID == OccupationMaster.OccupationID)
            )
            if crime_type:
                q = q.filter(CrimeSubHead.CrimeHeadName == crime_type)
            rows = (
                q.group_by(
                    CasteMaster.caste_master_name, ReligionMaster.ReligionName,
                    OccupationMaster.OccupationName, CrimeSubHead.CrimeHeadName,
                )
                .order_by(func.count(ComplainantDetails.ComplainantID).desc())
                .all()
            )
            return [
                {
                    "caste": r[0], "religion": r[1], "occupation": r[2],
                    "crime_type": r[3], "count": r[4],
                }
                for r in rows
            ]
        finally:
            session.close()
