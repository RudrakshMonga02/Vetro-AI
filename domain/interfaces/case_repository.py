"""
CaseRepository interface -- domain layer, zero external dependencies.
This is the seam that lets application/use-case code work against
either backend without ever importing SQLAlchemy or the Catalyst SDK:
  - Postgres/Supabase     -> infrastructure/persistence/postgres_repository.py
  - Catalyst Data Store   -> infrastructure/persistence/catalyst_repository.py

Application code (use-cases, routes) must only ever depend on this
interface. Swapping backends means swapping which implementation the
factory constructs (infrastructure/persistence/repository_factory.py),
never touching calling code.
"""
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any


class CaseRepository(ABC):
    """Abstract interface for reading/writing FIR case data, regardless
    of which underlying database engine actually stores it."""

    @abstractmethod
    def get_total_case_count(self) -> int:
        """Return the exact total number of cases. This must be a real
        COUNT query -- do NOT make callers derive this by summing a
        (possibly truncated) district/crime-type breakdown themselves,
        since that's exactly how the chatbot ended up reporting an
        unverified guess for 'how many cases do we have'."""
        ...

    @abstractmethod
    def get_accused_list(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return [{'accused_name': str, 'case_crime_no': str,
        'crime_type': str, ...}, ...] -- for 'list all accused/criminals'
        style questions. Without this, semantic search over case briefs
        is the only fallback, and case briefs don't contain accused
        names at all, so those questions fail even though the data
        exists in the Accused table."""
        ...

    @abstractmethod
    def get_case_by_id(self, case_id: int) -> dict[str, Any] | None:
        """Fetch a single case's full details."""
        ...

    @abstractmethod
    def get_district_counts(self) -> list[dict[str, Any]]:
        """Return [{'district': str, 'count': int}, ...] -- for hotspot map/charts."""
        ...

    @abstractmethod
    def get_crime_type_counts(self, district: str | None = None) -> list[dict[str, Any]]:
        """Return [{'crime_type': str, 'count': int}, ...], optionally filtered by district."""
        ...

    @abstractmethod
    def get_monthly_trend(
        self, district: str | None = None, crime_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Return [{'month': str, 'count': int}, ...] -- for trend charts / forecasting input.
        Both filters are optional and independent."""
        ...

    @abstractmethod
    def get_cases_for_map(
        self, limit: int = 5000, crime_type: str | None = None
    ) -> list[dict[str, Any]]:
        """Return [{'case_id': int, 'lat': float, 'lng': float, 'crime_type': str, 'date': str}, ...]
        for hotspot map, optionally filtered to one crime type. case_id lets the frontend
        deep-link a specific case into the Network Graph tab."""
        ...

    @abstractmethod
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
        """Return CaseMaster map records with both incident and registration
        timestamps plus CrimeMajorHeadID. The map route uses the same method
        for historical display filters and current early-warning analysis."""
        ...

    @abstractmethod
    def get_case_network(self, case_id: int) -> dict[str, Any]:
        """Return {'nodes', 'edges', 'case_context'} for a case's
        Victim/Accused/ArrestSurrender graph. Victim/accused node dicts
        include 'age'/'gender' alongside 'label' so a frontend detail
        panel doesn't need a second fetch.

        'case_context' is {'crime_type', 'district', 'date', 'brief'
        (truncated), 'mo_summary', 'keywords'} -- the last two are None/[]
        unless get_mo_extraction() already has a persisted row for this
        case. This is what lets a frontend hover tooltip show real case
        context with zero extra fetches, since it rides along on the one
        request the graph view already makes on load."""
        ...

    @abstractmethod
    def insert_case(self, case_data: dict[str, Any]) -> int:
        """Insert a new case row, return its new ID. Used by seeders/migration."""
        ...

    @abstractmethod
    def get_cross_case_links(self, accused_name: str) -> dict[str, Any]:
        """Find every case an accused with a matching name appears in.
        Returns {'accused_name': str, 'cases': [{'case_id', 'crime_no',
        'district', 'crime_type', 'date'}, ...], 'match_count': int,
        'match_basis': 'name'}.

        Name-matching only, deliberately -- there is no stable identity
        key for a person across cases anywhere in the ER diagram.
        Accused.PersonID is a per-case role label (A1/A2/A3), scoped to
        one CaseMasterID, not a cross-case identifier. So this is
        fuzzy/imperfect by construction (same-name-different-person
        false positives are possible, e.g. common names) -- callers
        must surface 'match_basis' to the user rather than presenting
        this as verified identity linkage."""
        ...

    @abstractmethod
    def get_repeat_offender_network(self, min_case_count: int = 2) -> list[dict[str, Any]]:
        """Return [{'accused_name': str, 'case_count': int, 'cases': [...],
        'risk_tier': str}, ...] for every accused name appearing in
        min_case_count+ distinct cases, ordered by case_count desc.
        The bulk/list counterpart to get_cross_case_links -- same
        name-matching caveat applies."""
        ...

    @abstractmethod
    def get_case_timeline(self, case_id: int) -> list[dict[str, Any]]:
        """Return chronologically-sorted events for one case, drawn from
        already-modeled dated fields: CrimeRegisteredDate, IncidentFromDate/
        IncidentToDate, InfoReceivedPSDate, each ArrestSurrender.ArrestSurrenderDate,
        and ChargesheetDetails.csdate if any exist for the case (this table isn't
        seeded per the project's own README, so implementations must handle zero
        chargesheet rows gracefully, not assume they exist).

        Shape: [{'date': str, 'label': str,
        'type': 'registered'|'incident_start'|'incident_end'|'info_received'
                |'arrest'|'chargesheet'}, ...], sorted ascending by date.
        Events with a null date are omitted rather than sorted arbitrarily."""
        ...

    @abstractmethod
    def get_investigative_leads(self, case_id: int) -> dict[str, Any]:
        """Purely structural lead-generation for one case -- no LLM call here,
        that's a separate, explicit, button-triggered step (see
        api/services/mo_extraction.py's suggest_leads()).

        Returns {'case_id': int, 'cross_case_links': [{'accused_name', 'case_id',
        'crime_no', 'district', 'crime_type', 'date'}, ...], 'similar_open_cases':
        [{'case_id', 'crime_no', 'district', 'crime_type', 'date', 'status'}, ...]}.

        cross_case_links: for every accused in this case, every OTHER case
        (excluding this one) a matching name appears in -- same name-matching
        caveat as get_cross_case_links(), which this reuses/wraps.
        similar_open_cases: other cases in the same district and crime type
        with an open status ('Under Investigation' or 'Undetected'), excluding
        this case -- 'worth comparing against', not a claim of any link."""
        ...

    @abstractmethod
    def get_sociological_breakdown(self, crime_type: str | None = None) -> list[dict[str, Any]]:
        """Return [{'caste': str|None, 'religion': str|None,
        'occupation': str|None, 'crime_type': str, 'count': int}, ...]
        joining ComplainantDetails against CasteMaster/ReligionMaster/
        OccupationMaster and the case's crime type, optionally filtered
        to one crime_type.

        This is COMPLAINANT-side demographic data only -- the schema
        has no equivalent caste/religion/occupation lookups on Accused
        or Victim. Callers must label this 'complainant demographics'
        in the UI, never 'offender demographics' -- the data doesn't
        support that claim and presenting it that way would be a
        seriously misleading criminological statement."""
        ...

    @abstractmethod
    def get_mo_extraction(self, case_id: int) -> dict[str, Any] | None:
        """Return {'mo_summary': str|None, 'keywords': list[str]} if this
        case already has a persisted MO (modus operandi) extraction, else
        None. Never triggers an LLM call itself -- pure DB read. See
        api/services/mo_extraction.py's extract_mo() for the LLM call
        that produces the values this stores."""
        ...

    @abstractmethod
    def save_mo_extraction(
        self, case_id: int, mo_summary: str | None, keywords: list[str]
    ) -> None:
        """Persist an already-extracted MO for this case. Upsert -- safe
        to call again for the same case_id (e.g. if a caller wants to
        re-extract), though nothing currently does that."""
        ...

    @abstractmethod
    def get_similar_mo_cases(
        self, case_id: int, keywords: list[str], min_shared: int = 2, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Return cases with the SAME crime sub-head as case_id (comparing
        MO across unrelated crime types, e.g. burglary vs cybercrime, is
        noise, not signal) that already have a persisted MO extraction
        (get_mo_extraction() returns non-None for them) AND share at least
        min_shared of the given keywords, excluding case_id itself.

        This is the one signal in this app that can link two cases with
        NO shared accused name -- e.g. two unsolved burglaries with the
        same rear-entry/nighttime/occupied-residence MO, before anyone's
        been identified in either. Deliberately does not extract MO for
        candidate cases that don't already have one -- see
        api/routes/offenders.py's /case/{id}/similar-mo for why (quota
        discipline: only compares against cases someone has already
        chosen to run 'Extract MO' on, never bulk-extracts).

        Returns [{'case_id', 'crime_no', 'district', 'crime_type', 'date',
        'shared_keywords': list[str], 'mo_summary'}, ...], sorted by
        number of shared keywords descending."""
        ...
