"""
Analytics routes: trend charts, crime-type breakdowns, district counts.
Repository layer has all the methods this needs (get_district_counts,
get_crime_type_counts, get_monthly_trend); this router calls them and
shapes the response. Results are cached (response_cache.py) since none
of this changes until new case data is seeded -- a manual, infrequent
operation, not something the running app ever writes.
"""
from fastapi import APIRouter, Depends
from api.middleware.auth import OfficerContext, get_current_officer

from api.services.forecasting import forecast_linear
from api.services.response_cache import cached_or_compute
from infrastructure.persistence.repository_factory import get_case_repository

router = APIRouter()


@router.get("/districts")
def district_counts(officer: OfficerContext = Depends(get_current_officer)):
    repo = get_case_repository()
    return cached_or_compute(f"analytics:districts:{officer.cache_key}", lambda: repo.get_district_counts(officer=officer))


@router.get("/crime-types")
def crime_type_counts(district: str | None = None, officer: OfficerContext = Depends(get_current_officer)):
    repo = get_case_repository()
    key = f"analytics:crime_types:{officer.cache_key}:{district or 'all'}"
    return cached_or_compute(key, lambda: repo.get_crime_type_counts(district=district, officer=officer))


@router.get("/trend")
def monthly_trend(district: str | None = None, crime_type: str | None = None, officer: OfficerContext = Depends(get_current_officer)):
    repo = get_case_repository()
    key = f"analytics:trend:{officer.cache_key}:{district or 'all'}:{crime_type or 'all'}"
    return cached_or_compute(key, lambda: repo.get_monthly_trend(district=district, crime_type=crime_type, officer=officer))


@router.get("/forecast")
def trend_forecast(
    district: str | None = None,
    crime_type: str | None = None,
    horizon: int = 3,
    lookback_months: int = 12,
    officer: OfficerContext = Depends(get_current_officer),
):
    """Returns {'history': [...], 'forecast': [...]} in one payload so
    the frontend can render one continuous chart line (actual, then
    dashed projected) without a second round-trip. forecast is [] when
    there's under 2 months of history -- not an error, just
    insufficient data to fit a trend line (see forecasting.py)."""
    def compute():
        repo = get_case_repository()
        trend = repo.get_monthly_trend(district=district, crime_type=crime_type, officer=officer)
        recent = trend[-lookback_months:] if lookback_months else trend
        forecast = forecast_linear(recent, horizon=horizon)
        return {"history": trend, "forecast": forecast}

    key = f"analytics:forecast:{officer.cache_key}:{district or 'all'}:{crime_type or 'all'}:{horizon}:{lookback_months}"
    return cached_or_compute(key, compute)
