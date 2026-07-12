import { useState, useEffect } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from "recharts";
import { apiGet } from "../../lib/apiClient";
import DistrictCrimeBreakdown from "./DistrictCrimeBreakdown";
import SociologicalBreakdown from "./SociologicalBreakdown";
import SeasonalPatternView from "./SeasonalPatternView";
import LoadingState from "../ui/LoadingState";
import {
  CHART_COLORS, tooltipContentStyle, tooltipLabelStyle, axisTickStyle, legendStyle,
} from "../../lib/chartTheme";

/** Merges {history, forecast} from /analytics/forecast into one series
 * recharts can draw as a single continuous line with a dashed tail:
 * every row carries both `actual` and `predicted` keys, only one of
 * which is set for any given month, so Line's connectNulls stays off
 * and the two segments render as visually distinct actual/projected. */
function mergeSeries(history, forecast) {
  const actualRows = history.map((h) => ({ month: h.month, actual: h.count }));
  if (forecast.length === 0) return actualRows;
  // Repeat the last actual point as the forecast line's starting point
  // so the dashed segment connects visually instead of floating apart.
  const bridge = { month: history[history.length - 1].month, predicted: history[history.length - 1].count };
  const forecastRows = forecast.map((f) => ({ month: f.month, predicted: f.predicted_count }));
  return [...actualRows, bridge, ...forecastRows];
}

export default function TrendsView() {
  const [districtList, setDistrictList] = useState([]);
  const [crimeTypeList, setCrimeTypeList] = useState([]);
  const [district, setDistrict] = useState("");
  const [crimeType, setCrimeType] = useState("");
  const [series, setSeries] = useState([]);
  const [loadingTrend, setLoadingTrend] = useState(true);

  useEffect(() => {
    apiGet("/analytics/districts").then((rows) => setDistrictList(rows.map((r) => r.district))).catch(() => {});
    apiGet("/analytics/crime-types").then((rows) => setCrimeTypeList(rows.map((r) => r.crime_type))).catch(() => {});
  }, []);

  useEffect(() => {
    setLoadingTrend(true);
    const params = new URLSearchParams({ horizon: "3" });
    if (district) params.set("district", district);
    if (crimeType) params.set("crime_type", crimeType);
    apiGet(`/analytics/forecast?${params.toString()}`)
      .then(({ history, forecast }) => setSeries(mergeSeries(history, forecast)))
      .catch((err) => console.error("Failed to load forecast:", err))
      .finally(() => setLoadingTrend(false));
  }, [district, crimeType]);

  return (
    <div className="h-full overflow-y-auto px-8 py-6 space-y-10">
      <div>
        <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
          <h2 className="font-mono text-xs uppercase tracking-wider text-accent">
            Monthly Case Volume &amp; Forecast
          </h2>
          <div className="flex gap-2">
            <select
              value={district}
              onChange={(e) => setDistrict(e.target.value)}
              className="bg-surface-panel border border-line rounded px-2 py-1 text-xs text-ink-secondary
                         font-mono focus:outline-none focus:border-accent"
            >
              <option value="">All Districts</option>
              {districtList.map((d) => (
                <option key={d} value={d}>{d}</option>
              ))}
            </select>
            <select
              value={crimeType}
              onChange={(e) => setCrimeType(e.target.value)}
              className="bg-surface-panel border border-line rounded px-2 py-1 text-xs text-ink-secondary
                         font-mono focus:outline-none focus:border-accent"
            >
              <option value="">All Crime Types</option>
              {crimeTypeList.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
        </div>
        <p className="text-[11px] text-ink-dim mb-3">
          Solid line: actual monthly counts. Dashed: a naive linear-trend
          projection, not a machine-learning model — treat it as a
          directional signal, not a precise prediction.
        </p>
        {loadingTrend ? (
          <div className="h-72"><LoadingState /></div>
        ) : (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={series} margin={{ left: 0, right: 16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} />
              <XAxis dataKey="month" tick={axisTickStyle} stroke={CHART_COLORS.axis} />
              <YAxis tick={axisTickStyle} stroke={CHART_COLORS.axis} />
              <Tooltip contentStyle={tooltipContentStyle} labelStyle={tooltipLabelStyle} />
              <Legend wrapperStyle={legendStyle} />
              <Line
                type="monotone"
                dataKey="actual"
                name="Actual"
                stroke={CHART_COLORS.primary}
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="predicted"
                name="Forecast"
                stroke={CHART_COLORS.secondary}
                strokeWidth={2}
                strokeDasharray="5 4"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div>
        <SeasonalPatternView />
      </div>

      <div>
        <DistrictCrimeBreakdown district={district || undefined} />
      </div>

      <div>
        <SociologicalBreakdown />
      </div>
    </div>
  );
}
