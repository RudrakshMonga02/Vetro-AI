"""
Catalyst Data Store implementation of CaseRepository, using ZCQL
(Catalyst's SQL-like query language) via the zcatalyst_sdk Python SDK.

IMPORTANT / UNTESTED: this file is written against Catalyst's documented
SDK interface (app.zcql().execute_query(), app.datastore().table(name)
.insert_row()/.insert_rows()), but has NOT been run against a real
Catalyst project from this environment (no network access to Catalyst's
API, no project credentials here). Treat this as a strong first draft --
run it against your actual Catalyst dev project and report back any
errors so we can fix real API mismatches.

Table names below assume you've created tables in the Catalyst console
with these exact names (case-sensitive, matching db/models.py naming
in PascalCase-free form -- Catalyst table names must be alphanumeric +
underscore, no special chars): CaseMaster, District, CrimeSubHead,
CrimeHead, CaseCategory, GravityOffence, CaseStatusMaster, Victim,
Accused, ArrestSurrender.

Known Catalyst dev-environment limits (confirmed from docs):
  - max 5,000 rows per table in dev environment
  - max 25,000 rows total per project in dev environment
Your full dummy dataset (2,500 cases + ~13,000 child rows + lookups)
exceeds this. Either trim the dummy dataset before migrating, or
request production environment access from organizers.
"""
import os
from typing import Any

import zcatalyst_sdk
from dotenv import load_dotenv

from domain.interfaces.case_repository import CaseRepository

load_dotenv()


def _get_app():
    """
    Initializes the Catalyst app instance. In a deployed Catalyst Function,
    zcatalyst_sdk.initialize() picks up credentials automatically from the
    execution environment. For local testing against a Catalyst project,
    you'll likely need admin credentials -- check Catalyst's "Local Testing"
    / Advanced I/O function docs for the exact env vars required
    (typically CATALYST_PROJECT_ID, service account / OAuth token).
    """
    return zcatalyst_sdk.initialize()


class CatalystCaseRepository(CaseRepository):

    def __init__(self):
        self.app = _get_app()
        self.zcql = self.app.zcql()
        self.datastore = self.app.datastore()

    def get_total_case_count(self) -> int:
        # NOTE: untested against a real Catalyst project -- verify ZCQL's
        # COUNT(*) syntax and result-row shape once credentials exist.
        result = self.zcql.execute_query("SELECT COUNT(CaseMasterID) FROM CaseMaster")
        if not result:
            return 0
        row = result[0]["CaseMaster"]
        # ZCQL typically returns the aggregate under a key like
        # "COUNT(CaseMasterID)" -- fall back to summing values defensively
        # in case the exact key name differs from what's assumed here.
        return int(next(iter(row.values()), 0))

    def get_accused_list(self, limit: int = 50) -> list[dict[str, Any]]:
        # NOTE: untested -- mirrors the Postgres version's join, but ZCQL's
        # join syntax/behavior should be confirmed against a live project.
        query = f"""
            SELECT Accused.AccusedName, Accused.AgeYear, Accused.GenderID,
                   CaseMaster.CrimeNo, CrimeSubHead.CrimeHeadName,
                   CaseStatusMaster.CaseStatusName
            FROM Accused
            JOIN CaseMaster ON Accused.CaseMasterID = CaseMaster.CaseMasterID
            JOIN CrimeSubHead ON CaseMaster.CrimeMinorHeadID = CrimeSubHead.CrimeSubHeadID
            JOIN CaseStatusMaster ON CaseMaster.CaseStatusID = CaseStatusMaster.CaseStatusID
            ORDER BY CaseMaster.CrimeRegisteredDate DESC
            LIMIT {limit}
        """
        rows = self.zcql.execute_query(query)
        return [
            {
                "accused_name": r["Accused"]["AccusedName"],
                "age": r["Accused"]["AgeYear"],
                "gender": r["Accused"]["GenderID"],
                "crime_no": r["CaseMaster"]["CrimeNo"],
                "crime_type": r["CrimeSubHead"]["CrimeHeadName"],
                "case_status": r["CaseStatusMaster"]["CaseStatusName"],
            }
            for r in rows
        ]

    def get_case_by_id(self, case_id: int) -> dict[str, Any] | None:
        query = f"""
            SELECT CaseMaster.CaseMasterID, CaseMaster.CrimeNo, CaseMaster.CrimeRegisteredDate,
                   District.DistrictName, CrimeSubHead.CrimeHeadName, CaseCategory.LookupValue,
                   GravityOffence.LookupValue, CaseStatusMaster.CaseStatusName,
                   CaseMaster.latitude, CaseMaster.longitude, CaseMaster.BriefFacts
            FROM CaseMaster
            JOIN District ON CaseMaster.DistrictID = District.DistrictID
            JOIN CrimeSubHead ON CaseMaster.CrimeMinorHeadID = CrimeSubHead.CrimeSubHeadID
            JOIN CaseCategory ON CaseMaster.CaseCategoryID = CaseCategory.CaseCategoryID
            JOIN GravityOffence ON CaseMaster.GravityOffenceID = GravityOffence.GravityOffenceID
            JOIN CaseStatusMaster ON CaseMaster.CaseStatusID = CaseStatusMaster.CaseStatusID
            WHERE CaseMaster.CaseMasterID = {case_id}
        """
        result = self.zcql.execute_query(query)
        if not result:
            return None
        row = result[0]  # ZCQL returns rows nested under table name keys, e.g. row['CaseMaster']['CaseMasterID']
        cm = row["CaseMaster"]
        return {
            "case_id": cm["CaseMasterID"], "crime_no": cm["CrimeNo"], "date": cm["CrimeRegisteredDate"],
            "district": row["District"]["DistrictName"],
            "crime_type": row["CrimeSubHead"]["CrimeHeadName"],
            "category": row["CaseCategory"]["LookupValue"],
            "gravity": row["GravityOffence"]["LookupValue"],
            "status": row["CaseStatusMaster"]["CaseStatusName"],
            "lat": float(cm["latitude"]) if cm.get("latitude") else None,
            "lng": float(cm["longitude"]) if cm.get("longitude") else None,
            "brief": cm.get("BriefFacts"),
        }

    def get_district_counts(self) -> list[dict[str, Any]]:
        query = """
            SELECT District.DistrictName, COUNT(CaseMaster.CaseMasterID)
            FROM CaseMaster
            JOIN District ON CaseMaster.DistrictID = District.DistrictID
            GROUP BY District.DistrictName
            ORDER BY COUNT(CaseMaster.CaseMasterID) DESC
        """
        result = self.zcql.execute_query(query)
        return [
            {
                "district": r["District"]["DistrictName"],
                "count": int(r["CaseMaster"]["COUNT(CaseMasterID)"]),
            }
            for r in result
        ]

    def get_crime_type_counts(self, district: str | None = None) -> list[dict[str, Any]]:
        query = """
            SELECT CrimeSubHead.CrimeHeadName, COUNT(CaseMaster.CaseMasterID)
            FROM CaseMaster
            JOIN CrimeSubHead ON CaseMaster.CrimeMinorHeadID = CrimeSubHead.CrimeSubHeadID
        """
        if district:
            query += f"""
            JOIN District ON CaseMaster.DistrictID = District.DistrictID
            WHERE District.DistrictName = '{district}'
            """
        query += " GROUP BY CrimeSubHead.CrimeHeadName ORDER BY COUNT(CaseMaster.CaseMasterID) DESC"

        result = self.zcql.execute_query(query)
        return [
            {
                "crime_type": r["CrimeSubHead"]["CrimeHeadName"],
                "count": int(r["CaseMaster"]["COUNT(CaseMasterID)"]),
            }
            for r in result
        ]

    def get_monthly_trend(self, district: str | None = None) -> list[dict[str, Any]]:
        # NOTE: ZCQL's date-formatting function support may differ from Postgres'
        # to_char(). Verify ZCQL's date/string function docs for the equivalent --
        # this may need adjustment once tested against a real project.
        query = """
            SELECT CaseMaster.CrimeRegisteredDate, COUNT(CaseMaster.CaseMasterID)
            FROM CaseMaster
        """
        if district:
            query += f"""
            JOIN District ON CaseMaster.DistrictID = District.DistrictID
            WHERE District.DistrictName = '{district}'
            """
        query += " GROUP BY CaseMaster.CrimeRegisteredDate ORDER BY CaseMaster.CrimeRegisteredDate"

        result = self.zcql.execute_query(query)
        # Collapse to YYYY-MM in Python since ZCQL date-truncation support is unconfirmed
        monthly: dict[str, int] = {}
        for r in result:
            date_str = r["CaseMaster"]["CrimeRegisteredDate"]
            month = str(date_str)[:7]
            count = int(r["CaseMaster"]["COUNT(CaseMasterID)"])
            monthly[month] = monthly.get(month, 0) + count
        return [{"month": m, "count": c} for m, c in sorted(monthly.items())]

    def get_cases_for_map(self, limit: int = 5000) -> list[dict[str, Any]]:
        query = f"""
            SELECT CaseMaster.latitude, CaseMaster.longitude,
                   CrimeSubHead.CrimeHeadName, CaseMaster.CrimeRegisteredDate
            FROM CaseMaster
            JOIN CrimeSubHead ON CaseMaster.CrimeMinorHeadID = CrimeSubHead.CrimeSubHeadID
            WHERE CaseMaster.latitude IS NOT NULL
            LIMIT 0,{limit}
        """
        result = self.zcql.execute_query(query)
        return [
            {
                "lat": float(r["CaseMaster"]["latitude"]),
                "lng": float(r["CaseMaster"]["longitude"]),
                "crime_type": r["CrimeSubHead"]["CrimeHeadName"],
                "date": str(r["CaseMaster"]["CrimeRegisteredDate"]),
            }
            for r in result
        ]

    def get_case_network(self, case_id: int) -> dict[str, Any]:
        victims = self.zcql.execute_query(
            f"SELECT VictimMasterID, VictimName FROM Victim WHERE CaseMasterID = {case_id}"
        )
        accused = self.zcql.execute_query(
            f"SELECT AccusedMasterID, AccusedName FROM Accused WHERE CaseMasterID = {case_id}"
        )

        nodes = [{"id": f"case_{case_id}", "label": f"Case {case_id}", "type": "case"}]
        edges = []
        for v in victims:
            vid = v["Victim"]["VictimMasterID"]
            nodes.append({"id": f"victim_{vid}", "label": v["Victim"]["VictimName"], "type": "victim"})
            edges.append({"source": f"case_{case_id}", "target": f"victim_{vid}"})
        for a in accused:
            aid = a["Accused"]["AccusedMasterID"]
            nodes.append({"id": f"accused_{aid}", "label": a["Accused"]["AccusedName"], "type": "accused"})
            edges.append({"source": f"case_{case_id}", "target": f"accused_{aid}"})

        # Arrest events for this case, and the junction table linking
        # each event to (potentially several) accused persons -- one
        # arrest event/raid can cover multiple accused, so this is a
        # two-hop query (ArrestSurrender -> InvArrestSurrenderAccused),
        # NOT a direct AccusedMasterID column on ArrestSurrender itself.
        # NOTE: untested against a real Catalyst project -- verify the
        # ZCQL syntax for the join/IN-subquery below once credentials exist.
        arrests = self.zcql.execute_query(
            f"SELECT ArrestSurrenderID, ArrestSurrenderDate FROM ArrestSurrender "
            f"WHERE CaseMasterID = {case_id}"
        )
        for ar in arrests:
            arrest_id = ar["ArrestSurrender"]["ArrestSurrenderID"]
            arrest_date = ar["ArrestSurrender"]["ArrestSurrenderDate"]
            nodes.append({
                "id": f"arrest_{arrest_id}",
                "label": f"Arrest {arrest_date}",
                "type": "arrest_event",
            })
            edges.append({
                "source": f"arrest_{arrest_id}",
                "target": f"case_{case_id}",
                "label": "arrest event for",
            })
            links = self.zcql.execute_query(
                f"SELECT AccusedMasterID, IsAccused FROM InvArrestSurrenderAccused "
                f"WHERE ArrestSurrenderID = {arrest_id}"
            )
            for link in links:
                aid = link["InvArrestSurrenderAccused"]["AccusedMasterID"]
                is_primary = link["InvArrestSurrenderAccused"]["IsAccused"]
                edges.append({
                    "source": f"accused_{aid}",
                    "target": f"arrest_{arrest_id}",
                    "label": "primary" if is_primary else "co-arrested",
                })
        return {"nodes": nodes, "edges": edges}

    def insert_case(self, case_data: dict[str, Any]) -> int:
        table = self.datastore.table("CaseMaster")
        row = table.insert_row(case_data)
        return row["ROWID"]
