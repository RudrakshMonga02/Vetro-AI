"""
Factory that decides which CaseRepository implementation to hand out,
based on the DATA_BACKEND env var. This is the one place in the whole
app that knows both backends exist -- application/presentation code
just calls get_case_repository() and uses the returned object through
the CaseRepository interface, never caring which backend is live.

Usage:
    DATA_BACKEND=postgres   -> PostgresCaseRepository (Supabase/local dev)
    DATA_BACKEND=catalyst   -> CatalystCaseRepository (production/submission)
"""
import os

from domain.interfaces.case_repository import CaseRepository


def get_case_repository() -> CaseRepository:
    backend = os.getenv("DATA_BACKEND", "postgres").lower()

    if backend == "postgres":
        from infrastructure.persistence.postgres_repository import PostgresCaseRepository
        return PostgresCaseRepository()

    if backend == "catalyst":
        from infrastructure.persistence.catalyst_repository import CatalystCaseRepository
        return CatalystCaseRepository()

    raise ValueError(f"Unknown DATA_BACKEND: {backend!r} (expected 'postgres' or 'catalyst')")
