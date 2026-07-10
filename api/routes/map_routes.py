"""
Hotspot map routes. STUB -- functional (calls the already-tested
repository method) but not yet optimized (e.g. no clustering/density
aggregation for large datasets). Good enough to wire up the frontend
map against; revisit once the real dataset's scale is known.
"""
from fastapi import APIRouter

from infrastructure.persistence.repository_factory import get_case_repository

router = APIRouter()


@router.get("/hotspots")
def hotspot_data(limit: int = 5000):
    repo = get_case_repository()
    return repo.get_cases_for_map(limit=limit)
