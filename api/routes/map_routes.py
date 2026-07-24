"""Spatiotemporal crime hotspot and emerging-cluster endpoints."""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from api.services.hotspot_intelligence import (
    BASELINE_WINDOW_DAYS,
    CURRENT_WINDOW_DAYS,
    build_hotspot_payload,
    resolve_incident_window,
    validate_hotspot_filters,
)
from api.middleware.auth import OfficerContext, get_current_officer
from infrastructure.persistence.repository_factory import get_case_repository

router = APIRouter()
logger = logging.getLogger(__name__)

# A hotspot request issues a display query and a 35-day early-warning query.
# Keeping each at most four 300-row Catalyst pages avoids exhausting the
# Advanced Function's 30-second window when a UI sends limit=5000.
MAX_MAP_QUERY_ROWS = 1000


@router.get("/hotspots")
def hotspot_data(
    limit: int = Query(default=500, ge=1, le=5000),
    crime_type: str | None = None,
    time_slot: str = "all",
    month: str | None = None,
    season: str | None = None,
    year: int | None = None,
    officer: OfficerContext = Depends(get_current_officer),
):
    """Return map incidents plus live, spatial early-warning clusters.

    Month/season filtering is executed by the repository against
    ``IncidentFromDate``. Time-of-day filtering happens after retrieval because
    Catalyst ZCQL does not provide a portable hour-extraction function across
    the SDK/database modes. The separate live analysis query is constrained by
    ``CrimeRegisteredDate`` for the last 35 days: seven current days and a
    28-day baseline.
    """
    effective_limit = min(limit, MAX_MAP_QUERY_ROWS)

    try:
        filters = validate_hotspot_filters(
            time_slot=time_slot,
            month=month,
            season=season,
            year=year,
            crime_type=crime_type,
        )
        repo = get_case_repository()
        incident_window = resolve_incident_window(filters)
        now = datetime.now()

        display_rows = repo.get_hotspot_records(
            limit=effective_limit,
            crime_type=filters.crime_type,
            incident_start=incident_window[0] if incident_window else None,
            incident_end=incident_window[1] if incident_window else None,
            officer=officer,
        )

        history_start = (now - timedelta(
            days=CURRENT_WINDOW_DAYS + BASELINE_WINDOW_DAYS
        )).date()
        history_end = (now + timedelta(days=1)).date()
        history_rows = repo.get_hotspot_records(
            limit=effective_limit,
            registered_start=history_start,
            registered_end=history_end,
            officer=officer,
        )

        payload = build_hotspot_payload(display_rows, history_rows, filters, now=now)
        payload["meta"].update({
            "security_scope": officer.cache_key,
            "requested_limit": limit,
            "effective_limit": effective_limit,
            "limit_capped": limit > effective_limit,
        })
        return payload
    except ValueError as error:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "INVALID_HOTSPOT_FILTER",
                    "message": str(error),
                }
            },
        )
    except OperationalError:
        # pool_pre_ping lets SQLAlchemy discard stale sockets before checkout,
        # but a server can still terminate a connection while executing. Return
        # a retryable API response instead of allowing an unhandled 500.
        logger.warning("Database connection failed during hotspot request", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "DATABASE_CONNECTION_BUSY",
                    "message": "Database connection busy, retrying...",
                }
            },
        )
    except Exception:
        # Do not expose Catalyst/Postgres details, but do log the full stack
        # trace on the server for diagnosis. Returning a response here ensures
        # CORSMiddleware can attach Access-Control-Allow-Origin to failures.
        logger.exception("Hotspot intelligence request failed")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "HOTSPOT_DATA_UNAVAILABLE",
                    "message": "Unable to load hotspot intelligence. Please retry shortly.",
                }
            },
        )
