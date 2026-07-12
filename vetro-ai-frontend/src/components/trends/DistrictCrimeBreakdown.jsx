import { useState, useEffect } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { apiGet } from "../../lib/apiClient";
import LoadingState from "../ui/LoadingState";
import {
  CHART_COLORS, tooltipContentStyle, tooltipLabelStyle, axisTickStyle, categoryTickStyle,
} from "../../lib/chartTheme";

function Chart({ title, data, dataKey, labelKey, loading }) {
  return (
    <div className="flex-1 min-w-0">
      <h3 className="font-mono text-[11px] uppercase tracking-wider text-ink-faint mb-2">
        {title}
      </h3>
      {loading ? (
        <div className="h-64"><LoadingState size="sm" /></div>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data.slice(0, 12)} layout="vertical" margin={{ left: 8, right: 16 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={CHART_COLORS.grid} horizontal={false} />
            <XAxis type="number" tick={axisTickStyle} stroke={CHART_COLORS.axis} />
            <YAxis
              type="category"
              dataKey={labelKey}
              tick={categoryTickStyle}
              stroke={CHART_COLORS.axis}
              width={120}
            />
            <Tooltip contentStyle={tooltipContentStyle} labelStyle={tooltipLabelStyle} />
            <Bar dataKey={dataKey} fill={CHART_COLORS.primary} radius={[0, 2, 2, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}

export default function DistrictCrimeBreakdown({ district }) {
  const [districts, setDistricts] = useState([]);
  const [crimeTypes, setCrimeTypes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const crimeTypeQuery = district ? `?district=${encodeURIComponent(district)}` : "";
    Promise.all([apiGet("/analytics/districts"), apiGet(`/analytics/crime-types${crimeTypeQuery}`)])
      .then(([d, c]) => {
        setDistricts(d);
        setCrimeTypes(c);
      })
      .catch((err) => console.error("Failed to load breakdown:", err))
      .finally(() => setLoading(false));
  }, [district]);

  return (
    <div className="flex gap-8 flex-wrap">
      <Chart title="Cases by District" data={districts} dataKey="count" labelKey="district" loading={loading} />
      <Chart
        title={district ? `Crime Types in ${district}` : "Cases by Crime Type"}
        data={crimeTypes}
        dataKey="count"
        labelKey="crime_type"
        loading={loading}
      />
    </div>
  );
}
