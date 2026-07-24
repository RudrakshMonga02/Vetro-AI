"""
Network graph routes (Cytoscape.js data). STUB -- functional for a
single case's Victim/Accused/ArrestSurrender relationships (repository
method already tested). Multi-case / cross-case graph traversal is not
built yet -- would need a new repository method if the demo wants to
show connections *between* cases (e.g. shared accused across FIRs).
"""
from fastapi import APIRouter, Depends, HTTPException

from api.middleware.auth import OfficerContext, get_current_officer

from infrastructure.persistence.repository_factory import get_case_repository

router = APIRouter()


@router.get("/case/{case_id}")
def case_network(case_id: int, officer: OfficerContext = Depends(get_current_officer)):
    repo = get_case_repository()
    if repo.get_case_by_id(case_id, officer=officer) is None:
        raise HTTPException(status_code=403, detail="Access Denied: Case outside officer jurisdiction.")
    result = repo.get_case_network(case_id)
    if not result["nodes"]:
        raise HTTPException(status_code=404, detail="Case not found or has no linked records")
    return result


@router.get("/case/{case_id}/timeline")
def case_timeline(case_id: int):
    repo = get_case_repository()
    events = repo.get_case_timeline(case_id)
    if not events:
        raise HTTPException(status_code=404, detail="Case not found or has no dated events")
    return events
