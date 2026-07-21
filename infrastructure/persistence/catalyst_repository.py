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
from datetime import date, datetime
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


def _zcql_datetime(value: datetime) -> str:
    """Format a Python datetime as the Catalyst ZCQL DateTime literal."""
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _escape_zcql_literal(value: str) -> str:
    """Quote a user-selected text filter before including it in ZCQL."""
    return value.replace("'", "''")


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
        limit = int(limit)  # defense-in-depth, see get_case_network's comment
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
        case_id = int(case_id)  # defense-in-depth, see get_case_network's comment
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

    def get_monthly_trend(
        self, district: str | None = None, crime_type: str | None = None
    ) -> list[dict[str, Any]]:
        # NOTE: ZCQL's date-formatting function support may differ from Postgres'
        # to_char(). Verify ZCQL's date/string function docs for the equivalent --
        # this may need adjustment once tested against a real project.
        # crime_type filter accepted for interface compatibility but not yet
        # wired into this query -- same untested status as the rest of this
        # module, see its docstring.
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

    def get_cases_for_map(
        self, limit: int = 5000, crime_type: str | None = None
    ) -> list[dict[str, Any]]:
        records = self.get_hotspot_records(limit=limit, crime_type=crime_type)
        return [
            {
                "case_id": record["case_id"],
                "lat": record["lat"],
                "lng": record["lng"],
                "crime_type": record["crime_type"],
                "date": str(record["crime_registered_date"]),
            }
            for record in records
        ]

    def get_hotspot_records(
        self,
        *,
        limit: int = 5000,
        crime_type: str | None = None,
        incident_start: datetime | None = None,
        incident_end: datetime | None = None,
        registered_start: date | None = None,
        registered_end: date | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch schema-grounded map points through ZCQL.

        Catalyst permits at most 300 SELECT rows per request, therefore this
        method pages results rather than silently dropping records. Every value
        interpolated into the query is either an internally constructed date or
        an escaped crime-type filter.
        """
        conditions = [
            "CaseMaster.latitude IS NOT NULL",
            "CaseMaster.longitude IS NOT NULL",
        ]

        if incident_start:
            conditions.append(
                f"CaseMaster.IncidentFromDate >= '{_zcql_datetime(incident_start)}'"
            )
        if incident_end:
            conditions.append(
                f"CaseMaster.IncidentFromDate < '{_zcql_datetime(incident_end)}'"
            )
        if registered_start:
            conditions.append(
                f"CaseMaster.CrimeRegisteredDate >= '{registered_start.isoformat()}'"
            )
        if registered_end:
            conditions.append(
                f"CaseMaster.CrimeRegisteredDate < '{registered_end.isoformat()}'"
            )
        if crime_type:
            conditions.append(
                "CrimeSubHead.CrimeHeadName = "
                f"'{_escape_zcql_literal(crime_type)}'"
            )

        order_column = (
            "CaseMaster.IncidentFromDate"
            if incident_start or incident_end
            else "CaseMaster.CrimeRegisteredDate"
        )
        select_prefix = f"""
            SELECT CaseMaster.CaseMasterID, CaseMaster.latitude, CaseMaster.longitude,
                   CaseMaster.CrimeMajorHeadID, CaseMaster.IncidentFromDate,
                   CaseMaster.CrimeRegisteredDate, CrimeSubHead.CrimeHeadName
            FROM CaseMaster
            JOIN CrimeSubHead ON CaseMaster.CrimeMinorHeadID = CrimeSubHead.CrimeSubHeadID
            WHERE {' AND '.join(conditions)}
            ORDER BY {order_column} DESC
        """

        rows: list[dict[str, Any]] = []
        offset = 0
        safe_limit = max(1, min(int(limit), 5000))

        while offset < safe_limit:
            page_size = min(300, safe_limit - offset)
            query = f"{select_prefix} LIMIT {offset},{page_size}"
            page = self.zcql.execute_query(query)
            if not page:
                break

            rows.extend(page)
            if len(page) < page_size:
                break
            offset += len(page)

        return [
            {
                "case_id": row["CaseMaster"]["CaseMasterID"],
                "lat": float(row["CaseMaster"]["latitude"]),
                "lng": float(row["CaseMaster"]["longitude"]),
                "crime_type": row["CrimeSubHead"]["CrimeHeadName"],
                "crime_major_head_id": row["CaseMaster"].get("CrimeMajorHeadID"),
                "incident_from_date": row["CaseMaster"].get("IncidentFromDate"),
                "crime_registered_date": row["CaseMaster"].get("CrimeRegisteredDate"),
            }
            for row in rows
        ]

    def get_case_network(self, case_id: int) -> dict[str, Any]:
        # KNOWN GAP vs. postgres_repository.py: the Postgres implementation
        # now flags accused nodes with cross_case/case_count (a same-name
        # distinct-CaseMasterID count) -- this draft does not yet do the
        # equivalent ZCQL query. Untested against a real Catalyst project
        # either way; add this when this backend actually gets implemented
        # for real rather than guessing ZCQL aggregate syntax blind.
        #
        # Defense-in-depth: cast explicitly rather than trusting that
        # every future caller of this method goes through a route with
        # `case_id: int` type coercion (see docs/PRD.md vulnerability
        # review -- these ZCQL queries are built via f-string
        # interpolation, not parameter binding, since the exact ZCQL
        # bind-parameter syntax hasn't been confirmed against a real
        # Catalyst project yet; forcing int() here means even a
        # malformed/string case_id can only ever produce a valid
        # integer or raise ValueError, never inject arbitrary SQL/ZCQL).
        case_id = int(case_id)

        victims = self.zcql.execute_query(
            f"SELECT VictimMasterID, VictimName, AgeYear, GenderID FROM Victim "
            f"WHERE CaseMasterID = {case_id}"
        )
        accused = self.zcql.execute_query(
            f"SELECT AccusedMasterID, AccusedName, AgeYear, GenderID FROM Accused "
            f"WHERE CaseMasterID = {case_id}"
        )

        nodes = [{"id": f"case_{case_id}", "label": f"Case {case_id}", "type": "case"}]
        edges = []
        for v in victims:
            vid = v["Victim"]["VictimMasterID"]
            nodes.append({
                "id": f"victim_{vid}", "label": v["Victim"]["VictimName"], "type": "victim",
                "age": v["Victim"].get("AgeYear"), "gender": v["Victim"].get("GenderID"),
            })
            edges.append({"source": f"case_{case_id}", "target": f"victim_{vid}"})
        for a in accused:
            aid = a["Accused"]["AccusedMasterID"]
            nodes.append({
                "id": f"accused_{aid}", "label": a["Accused"]["AccusedName"], "type": "accused",
                "age": a["Accused"].get("AgeYear"), "gender": a["Accused"].get("GenderID"),
            })
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
            arrest_id = int(ar["ArrestSurrender"]["ArrestSurrenderID"])  # defense-in-depth, see above
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

    def get_cross_case_links(self, accused_name: str) -> dict[str, Any]:
        # NOT YET IMPLEMENTED against a real Catalyst project -- Data
        # Store integration is deferred (see docs/PRD.md). Exists only
        # so CatalystCaseRepository still satisfies the CaseRepository
        # ABC and can be instantiated; DATA_BACKEND=catalyst must not
        # be selected until this is filled in.
        raise NotImplementedError(
            "get_cross_case_links: Catalyst Data Store backend not yet implemented"
        )

    def get_repeat_offender_network(self, min_case_count: int = 2) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "get_repeat_offender_network: Catalyst Data Store backend not yet implemented"
        )

    def get_case_timeline(self, case_id: int) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "get_case_timeline: Catalyst Data Store backend not yet implemented"
        )

    def get_investigative_leads(self, case_id: int) -> dict[str, Any]:
        raise NotImplementedError(
            "get_investigative_leads: Catalyst Data Store backend not yet implemented"
        )

    def get_sociological_breakdown(self, crime_type: str | None = None) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "get_sociological_breakdown: Catalyst Data Store backend not yet implemented"
        )

    def get_mo_extraction(self, case_id: int) -> dict[str, Any] | None:
        raise NotImplementedError(
            "get_mo_extraction: Catalyst Data Store backend not yet implemented"
        )

    def save_mo_extraction(
        self, case_id: int, mo_summary: str | None, keywords: list[str]
    ) -> None:
        raise NotImplementedError(
            "save_mo_extraction: Catalyst Data Store backend not yet implemented"
        )

    def get_similar_mo_cases(
        self, case_id: int, keywords: list[str], min_shared: int = 2, limit: int = 10
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(
            "get_similar_mo_cases: Catalyst Data Store backend not yet implemented"
        )
