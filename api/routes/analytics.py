"""
Analytics routes: trend charts, crime-type breakdowns, district counts.
STUB -- not yet built out. Repository layer (Stage 1) already has all
the methods this needs (get_district_counts, get_crime_type_counts,
get_monthly_trend); this router just needs to call them and shape the
response. Building this out is next after /chat is solid.
"""
from fastapi import APIRouter

from infrastructure.persistence.repository_factory import get_case_repository

router = APIRouter()


@router.get("/districts")
def district_counts():
    repo = get_case_repository()
    return repo.get_district_counts()


@router.get("/crime-types")
def crime_type_counts(district: str | None = None):
    repo = get_case_repository()
    return repo.get_crime_type_counts(district=district)


@router.get("/trend")
def monthly_trend(district: str | None = None):
    repo = get_case_repository()
    return repo.get_monthly_trend(district=district)
