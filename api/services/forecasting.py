"""
Naive trend-extrapolation forecasting. Per docs/PRD.md's own call: "a
naive trend extrapolation is enough to demonstrate predictive insight
without building real ML infra" given the timeline/synthetic-data
constraints. Pure function over CaseRepository.get_monthly_trend()'s
output -- no ML dependency, no Catalyst Cron -- computed synchronously
on request. Cron scheduling (the one genuinely Catalyst-only piece of
"forecasting" as a product feature) is deferred along with the rest of
Data Store integration; everything else here has no Catalyst
dependency to begin with.
"""
from typing import Any


def forecast_linear(monthly_counts: list[dict[str, Any]], horizon: int = 3) -> list[dict[str, Any]]:
    """Simple least-squares linear regression over month-index -> count,
    projected `horizon` months past the last observed month. Returns
    [] if there isn't enough data (fewer than 2 months) to fit a line
    -- callers should treat that as "insufficient data", not an error.
    """
    n = len(monthly_counts)
    if n < 2:
        return []

    xs = list(range(n))
    ys = [row["count"] for row in monthly_counts]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denominator = sum((x - mean_x) ** 2 for x in xs) or 1
    slope = numerator / denominator
    intercept = mean_y - slope * mean_x

    last_year, last_month = map(int, monthly_counts[-1]["month"].split("-"))

    forecast = []
    year, month = last_year, last_month
    for i in range(1, horizon + 1):
        month += 1
        if month > 12:
            month = 1
            year += 1
        predicted = max(0, round(intercept + slope * (n - 1 + i)))
        forecast.append({"month": f"{year:04d}-{month:02d}", "predicted_count": predicted})

    return forecast
