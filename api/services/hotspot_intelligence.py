"""Pure spatiotemporal hotspot analysis used by the map API.

The repository adapters only retrieve schema-backed CaseMaster records.
This module applies time-of-day filtering and detects anomalous, recent
spatial clusters without coupling the route to PostgreSQL or Catalyst.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import asin, ceil, cos, radians, sin, sqrt
from typing import Any
from zoneinfo import ZoneInfo


BUSINESS_TIME_ZONE = ZoneInfo("Asia/Kolkata")
CURRENT_WINDOW_DAYS = 7
BASELINE_WINDOW_DAYS = 28
CLUSTER_RADIUS_METRES = 300
MIN_EMERGING_INCIDENTS = 4  # More than three incidents.

TIME_SLOTS: dict[str, tuple[int, int] | None] = {
    "all": None,
    "night": (0, 6),
    "morning": (6, 12),
    "afternoon": (12, 18),
    "evening": (18, 24),
}

# Seasons are contiguous month ranges. Winter deliberately crosses into the
# following calendar year, which resolve_incident_window() handles.
SEASONS: dict[str, tuple[int, int]] = {
    "summer": (3, 3),
    "monsoon": (6, 4),
    "post_monsoon": (10, 2),
    "winter": (12, 3),
}


@dataclass(frozen=True)
class HotspotFilters:
    time_slot: str
    month: int | None
    season: str | None
    year: int
    crime_type: str | None


@dataclass(frozen=True)
class MapIncident:
    case_id: int
    lat: float
    lng: float
    crime_type: str
    crime_major_head_id: str
    incident_at: datetime | None
    registered_at: datetime | None


def validate_hotspot_filters(
    *,
    time_slot: str,
    month: str | None,
    season: str | None,
    year: int | None,
    crime_type: str | None,
) -> HotspotFilters:
    normalized_slot = time_slot.lower().strip()
    if normalized_slot not in TIME_SLOTS:
        raise ValueError("time_slot must be all, night, morning, afternoon, or evening.")

    normalized_month: int | None = None
    if month is not None:
        if not month.isdigit() or not 1 <= int(month) <= 12:
            raise ValueError("month must be between 01 and 12.")
        normalized_month = int(month)

    normalized_season = season.lower().strip() if season else None
    if normalized_season and normalized_season not in SEASONS:
        raise ValueError("season must be summer, monsoon, post_monsoon, or winter.")

    if normalized_month and normalized_season:
        raise ValueError("Use either month or season, not both.")

    current_year = datetime.now(BUSINESS_TIME_ZONE).year
    normalized_year = current_year if year is None else year
    if not 2015 <= normalized_year <= current_year + 1:
        raise ValueError("year must be a valid reporting year.")

    return HotspotFilters(
        time_slot=normalized_slot,
        month=normalized_month,
        season=normalized_season,
        year=normalized_year,
        crime_type=crime_type.strip() if crime_type else None,
    )


def resolve_incident_window(filters: HotspotFilters) -> tuple[datetime, datetime] | None:
    """Return a local [start, end) window for the selected month or season."""
    if filters.month:
        start = datetime(filters.year, filters.month, 1)
        end = _add_months(start, 1)
        return start, end

    if filters.season:
        start_month, duration = SEASONS[filters.season]
        start = datetime(filters.year, start_month, 1)
        return start, _add_months(start, duration)

    return None


def build_hotspot_payload(
    display_rows: list[dict[str, Any]],
    history_rows: list[dict[str, Any]],
    filters: HotspotFilters,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create the response consumed by HotspotMapView.

    `display_rows` already had the month/season range applied by the repository.
    `history_rows` is intentionally unfiltered by historical UI filters so that
    early warnings always describe the current operational picture.
    """
    reference_time = _as_local_naive(now or datetime.now(BUSINESS_TIME_ZONE))
    display_incidents = [
        incident
        for row in display_rows
        if (incident := _normalize_incident(row)) is not None
        and _matches_time_slot(incident.incident_at, filters.time_slot)
    ]
    history_incidents = [
        incident
        for row in history_rows
        if (incident := _normalize_incident(row)) is not None
    ]

    emerging_clusters = _detect_emerging_clusters(history_incidents, reference_time)
    emerging_case_ids = {
        case_id
        for cluster in emerging_clusters
        for case_id in cluster.pop("_member_ids")
    }

    incidents = [
        {
            "case_id": incident.case_id,
            "lat": incident.lat,
            "lng": incident.lng,
            "crime_type": incident.crime_type,
            "crime_major_head_id": incident.crime_major_head_id,
            "incident_from_date": _serialize_datetime(incident.incident_at),
            "crime_registered_date": _serialize_datetime(incident.registered_at),
            "is_emerging": incident.case_id in emerging_case_ids,
        }
        for incident in display_incidents
    ]

    return {
        "incidents": incidents,
        "emergingClusters": emerging_clusters,
        "meta": {
            "filters": {
                "time_slot": filters.time_slot,
                "month": f"{filters.month:02d}" if filters.month else None,
                "season": filters.season,
                "year": filters.year,
                "crime_type": filters.crime_type,
            },
            "returned_incidents": len(incidents),
            "warning_window_days": CURRENT_WINDOW_DAYS,
        },
    }


def _normalize_incident(row: dict[str, Any]) -> MapIncident | None:
    try:
        lat = float(row["lat"])
        lng = float(row["lng"])
        if not -90 <= lat <= 90 or not -180 <= lng <= 180:
            return None
        return MapIncident(
            case_id=int(row["case_id"]),
            lat=lat,
            lng=lng,
            crime_type=str(row.get("crime_type") or "Unknown crime type"),
            crime_major_head_id=str(row.get("crime_major_head_id") or "Unknown"),
            incident_at=_parse_datetime(row.get("incident_from_date")),
            registered_at=_parse_datetime(row.get("crime_registered_date")),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _as_local_naive(value)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    text = str(value).strip()
    if not text:
        return None

    try:
        return _as_local_naive(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        pass

    for pattern in ("%Y-%m-%d %H:%M:%S:%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


def _as_local_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(BUSINESS_TIME_ZONE).replace(tzinfo=None)


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat(sep=" ", timespec="seconds") if value else None


def _matches_time_slot(incident_at: datetime | None, time_slot: str) -> bool:
    if time_slot == "all":
        return True
    if incident_at is None:
        return False
    start_hour, end_hour = TIME_SLOTS[time_slot] or (0, 24)
    return start_hour <= incident_at.hour < end_hour


def _detect_emerging_clusters(
    incidents: list[MapIncident],
    now: datetime,
) -> list[dict[str, Any]]:
    current_start = now - timedelta(days=CURRENT_WINDOW_DAYS)
    baseline_start = current_start - timedelta(days=BASELINE_WINDOW_DAYS)
    history = [
        incident
        for incident in incidents
        if incident.registered_at and baseline_start <= incident.registered_at < now
    ]

    warnings: list[dict[str, Any]] = []
    for cluster in _make_spatial_clusters(history):
        recent = [item for item in cluster["members"] if item.registered_at >= current_start]
        baseline = [
            item
            for item in cluster["members"]
            if baseline_start <= item.registered_at < current_start
        ]
        expected_weekly_baseline = (
            len(baseline) / BASELINE_WINDOW_DAYS * CURRENT_WINDOW_DAYS
        )
        anomaly_threshold = max(
            MIN_EMERGING_INCIDENTS,
            ceil(expected_weekly_baseline * 2),
        )

        if len(recent) < anomaly_threshold:
            continue

        lat, lng = _centroid(recent)
        crime_type = Counter(item.crime_type for item in recent).most_common(1)[0][0]
        warnings.append(
            {
                "cluster_id": f"{cluster['crime_major_head_id']}:{lat:.4f}:{lng:.4f}",
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "crime_major_head_id": cluster["crime_major_head_id"],
                "crime_type": crime_type,
                "recent_incident_count": len(recent),
                "expected_weekly_baseline": round(expected_weekly_baseline, 1),
                "window_start": _serialize_datetime(current_start),
                "window_end": _serialize_datetime(now),
                "_member_ids": [item.case_id for item in recent],
            }
        )

    return sorted(warnings, key=lambda item: item["recent_incident_count"], reverse=True)


def _make_spatial_clusters(incidents: list[MapIncident]) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []

    for incident in incidents:
        nearest: dict[str, Any] | None = None
        nearest_distance = float("inf")

        for cluster in clusters:
            if cluster["crime_major_head_id"] != incident.crime_major_head_id:
                continue
            distance = _haversine_metres(incident.lat, incident.lng, cluster["lat"], cluster["lng"])
            if distance <= CLUSTER_RADIUS_METRES and distance < nearest_distance:
                nearest = cluster
                nearest_distance = distance

        if nearest is None:
            clusters.append(
                {
                    "lat": incident.lat,
                    "lng": incident.lng,
                    "crime_major_head_id": incident.crime_major_head_id,
                    "members": [incident],
                }
            )
            continue

        count = len(nearest["members"])
        nearest["lat"] = (nearest["lat"] * count + incident.lat) / (count + 1)
        nearest["lng"] = (nearest["lng"] * count + incident.lng) / (count + 1)
        nearest["members"].append(incident)

    return clusters


def _centroid(incidents: list[MapIncident]) -> tuple[float, float]:
    return (
        sum(item.lat for item in incidents) / len(incidents),
        sum(item.lng for item in incidents) / len(incidents),
    )


def _haversine_metres(lat_a: float, lng_a: float, lat_b: float, lng_b: float) -> float:
    earth_radius = 6_371_000
    delta_lat = radians(lat_b - lat_a)
    delta_lng = radians(lng_b - lng_a)
    value = (
        sin(delta_lat / 2) ** 2
        + cos(radians(lat_a)) * cos(radians(lat_b)) * sin(delta_lng / 2) ** 2
    )
    return 2 * earth_radius * asin(sqrt(value))


def _add_months(value: datetime, months: int) -> datetime:
    absolute_month = value.year * 12 + (value.month - 1) + months
    year, month_index = divmod(absolute_month, 12)
    return datetime(year, month_index + 1, 1)
