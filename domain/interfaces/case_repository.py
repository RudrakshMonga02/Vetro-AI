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
    def get_monthly_trend(self, district: str | None = None) -> list[dict[str, Any]]:
        """Return [{'month': str, 'count': int}, ...] -- for trend charts / forecasting input."""
        ...

    @abstractmethod
    def get_cases_for_map(self, limit: int = 5000) -> list[dict[str, Any]]:
        """Return [{'lat': float, 'lng': float, 'crime_type': str, ...}, ...] for hotspot map."""
        ...

    @abstractmethod
    def get_case_network(self, case_id: int) -> dict[str, Any]:
        """Return nodes/edges for a case's Victim/Accused/ArrestSurrender graph."""
        ...

    @abstractmethod
    def insert_case(self, case_data: dict[str, Any]) -> int:
        """Insert a new case row, return its new ID. Used by seeders/migration."""
        ...
