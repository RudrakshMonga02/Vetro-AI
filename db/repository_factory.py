"""
Factory that decides which CaseRepository implementation to hand out,
based on the DATA_BACKEND env var. This is the one place in the whole
app that knows both backends exist -- routes/services just call
get_case_repository() and use the returned object through the
CaseRepository interface, never caring which backend is live.

Usage:
    DATA_BACKEND=postgres   -> PostgresCaseRepository (Supabase/local dev)
    DATA_BACKEND=catalyst   -> CatalystCaseRepository (production/submission)
"""
import os

from db.repository_base import CaseRepository


def get_case_repository() -> CaseRepository:
    backend = os.getenv("DATA_BACKEND", "postgres").lower()

    if backend == "postgres":
        from db.repository_postgres import PostgresCaseRepository
        return PostgresCaseRepository()

    if backend == "catalyst":
        from catalyst.repository_catalyst import CatalystCaseRepository
        return CatalystCaseRepository()

    raise ValueError(f"Unknown DATA_BACKEND: {backend!r} (expected 'postgres' or 'catalyst')")
