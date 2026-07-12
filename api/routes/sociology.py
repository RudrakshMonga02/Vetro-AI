"""
Sociological crime insights: complainant-side demographic breakdowns
(caste/religion/occupation x crime type).

Deliberately its own router rather than folded into analytics.py --
this joins a genuinely different part of the schema (ComplainantDetails
+ its lookup tables) than analytics.py's district/crime-type/trend
triad, and "complainant demographics" needs to stay visually/textually
distinct from "crime analytics" in the UI given how easily this class
of data gets over-interpreted (see the repository method's own
docstring: this is COMPLAINANT demographics, never "offender
demographics" -- the schema has no caste/religion/occupation lookups
on Accused or Victim at all).

Known data-quality caveat, worth repeating at the API layer: the
current dataset is Faker-seeded synthetic data (see db/seed_cases.py),
so any correlation shown here is a demo artifact, not a real
sociological finding -- the frontend must carry a visible disclaimer,
not just this comment.
"""
from fastapi import APIRouter

from api.services.response_cache import cached_or_compute
from infrastructure.persistence.repository_factory import get_case_repository

router = APIRouter()


@router.get("/breakdown")
def sociological_breakdown(crime_type: str | None = None):
    repo = get_case_repository()
    key = f"sociology:breakdown:{crime_type or 'all'}"
    return cached_or_compute(key, lambda: repo.get_sociological_breakdown(crime_type=crime_type))
