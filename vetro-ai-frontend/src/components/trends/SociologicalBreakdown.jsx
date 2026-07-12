import { useState, useEffect, useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { AlertTriangle } from "lucide-react";
import { apiGet } from "../../lib/apiClient";
import LoadingState from "../ui/LoadingState";
import {
  CHART_COLORS, tooltipContentStyle, tooltipLabelStyle, axisTickStyle, categoryTickStyle,
} from "../../lib/chartTheme";

const DIMENSIONS = [
  { key: "caste", label: "Caste" },
  { key: "religion", label: "Religion" },
  { key: "occupation", label: "Occupation" },
];

function aggregateBy(rows, dimension) {
  const totals = new Map();
  for (const row of rows) {
    const key = row[dimension] ?? "Unspecified";
    totals.set(key, (totals.get(key) || 0) + row.count);
  }
  return Array.from(totals.entries())
    .map(([label, count]) => ({ label, count }))
    .sort((a, b) => b.count - a.count);
}

export default function SociologicalBreakdown() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dimension, setDimension] = useState("caste");

  useEffect(() => {
    apiGet("/sociology/breakdown")
      .then(setRows)
      .catch((err) => console.error("Failed to load sociological breakdown:", err))
      .finally(() => setLoading(false));
  }, []);

  const chartData = useMemo(() => aggregateBy(rows, dimension), [rows, dimension]);

  return (
    <div>
      <div className="flex items-start justify-between gap-4 mb-3 flex-wrap">
        <div>
          <h3 className="font-mono text-[11px] uppercase tracking-wider text-ink-faint">
            Complainant Demographics by Crime Type
          </h3>
          <p className="text-[11px] text-ink-dim mt-1 max-w-md leading-snug">
            Complainant-side data only — the schema has no caste/religion/
            occupation lookups on accused or victim records. Never read
            this as offender demographics.
          </p>
        </div>
        <div className="flex gap-1">
          {DIMENSIONS.map((d) => (
            <button
              key={d.key}
              onClick={() => setDimension(d.key)}
              className={`text-[10px] font-mono uppercase tracking-wider px-2 py-1 rounded border transition-colors ${
                dimension === d.key
                  ? "border-accent text-accent"
                  : "border-line text-ink-faint hover:text-ink-secondary"
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-start gap-2 bg-status-error/10 border border-status-error/40 rounded px-3 py-2 mb-4">
        <AlertTriangle className="w-3.5 h-3.5 text-status-error shrink-0 mt-0.5" />
        <p className="text-[11px] text-ink-secondary leading-snug">
          Built on Faker-generated synthetic demo data — any pattern shown
          here is a data artifact, not a real sociological finding.
        </p>
      </div>

      {loading ? (
        <div className="h-64"><LoadingState size="sm" /></div>
      ) : (
        <ResponsiveContainer width="100%" height={280}>
          <BarChart data={chartData.slice(0, 15)} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} horizontal={false} />
            <XAxis type="number" tick={axisTickStyle} stroke={CHART_COLORS.axis} />
            <YAxis
              type="category"
              dataKey="label"
              tick={categoryTickStyle}
              stroke={CHART_COLORS.axis}
              width={120}
            />
            <Tooltip contentStyle={tooltipContentStyle} labelStyle={tooltipLabelStyle} />
            <Bar dataKey="count" fill={CHART_COLORS.secondary} radius={[0, 2, 2, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
