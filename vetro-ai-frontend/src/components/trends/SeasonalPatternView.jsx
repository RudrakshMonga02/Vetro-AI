import { useState, useEffect, useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { apiGet } from "../../lib/apiClient";
import LoadingState from "../ui/LoadingState";
import {
  CHART_COLORS, tooltipContentStyle, tooltipLabelStyle, axisTickStyle,
} from "../../lib/chartTheme";

const MONTH_LABELS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** Directly answers the problem statement's "seasonal and event-based
 * crime trend analysis" ask, which nothing else in this app addresses.
 * Computed entirely client-side from the full, unfiltered monthly
 * trend history -- no new backend endpoint. Groups every "YYYY-MM"
 * bucket by its calendar month and averages across however many years
 * of data exist, so a spike that only ever happened once doesn't
 * masquerade as a seasonal pattern. */
function computeSeasonalAverages(monthlyTrend) {
  const sums = Array(12).fill(0);
  const yearsSeen = Array(12).fill(0).map(() => new Set());

  for (const row of monthlyTrend) {
    const [year, month] = row.month.split("-").map(Number);
    const idx = month - 1;
    sums[idx] += row.count;
    yearsSeen[idx].add(year);
  }

  return MONTH_LABELS.map((label, idx) => ({
    label,
    average: yearsSeen[idx].size > 0 ? Math.round((sums[idx] / yearsSeen[idx].size) * 10) / 10 : 0,
    yearsOfData: yearsSeen[idx].size,
  }));
}

export default function SeasonalPatternView() {
  const [monthlyTrend, setMonthlyTrend] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Deliberately unfiltered -- this view is about the shape of the
    // full dataset's calendar-year pattern, not one district/crime type.
    apiGet("/analytics/trend")
      .then(setMonthlyTrend)
      .catch((err) => console.error("Failed to load trend for seasonal view:", err))
      .finally(() => setLoading(false));
  }, []);

  const seasonal = useMemo(() => computeSeasonalAverages(monthlyTrend), [monthlyTrend]);
  const yearsSpan = useMemo(() => {
    const years = new Set(monthlyTrend.map((r) => r.month.split("-")[0]));
    return years.size;
  }, [monthlyTrend]);

  return (
    <div>
      <h3 className="font-mono text-[11px] uppercase tracking-wider text-ink-faint mb-1">
        Seasonal Pattern — Average Cases by Month
      </h3>
      <p className="text-[11px] text-ink-dim mb-3">
        Every "{"{"}"YYYY-MM{"}"}" bucket in the full case history, averaged by calendar month
        across {yearsSpan || "…"} year{yearsSpan === 1 ? "" : "s"} of data — not one district or
        crime type, the whole dataset's yearly rhythm.
      </p>
      {loading ? (
        <div className="h-64"><LoadingState size="sm" /></div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={seasonal} margin={{ left: 0, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} vertical={false} />
            <XAxis dataKey="label" tick={axisTickStyle} stroke={CHART_COLORS.axis} />
            <YAxis tick={axisTickStyle} stroke={CHART_COLORS.axis} />
            <Tooltip
              contentStyle={tooltipContentStyle}
              labelStyle={tooltipLabelStyle}
              formatter={(value) => [value, "Avg. cases"]}
            />
            <Bar dataKey="average" fill={CHART_COLORS.primary} radius={[2, 2, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
