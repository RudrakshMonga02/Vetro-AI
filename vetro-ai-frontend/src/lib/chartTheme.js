// Shared recharts styling -- previously copy-pasted with slightly
// different values across DistrictCrimeBreakdown.jsx,
// SociologicalBreakdown.jsx, and TrendsView.jsx.

export const CHART_COLORS = {
  grid: "#2A3348",
  axis: "#2A3348",
  axisText: "#6B7488",
  labelText: "#A8AEC0",
  primary: "#D4A24C",
  secondary: "#5B8DB8",
  error: "#B0503C",
};

export const tooltipContentStyle = {
  backgroundColor: "#151B2E",
  border: "1px solid #2A3348",
  borderRadius: 4,
  fontSize: 11,
  fontFamily: "monospace",
};

export const tooltipLabelStyle = { color: "#E4E7EC" };

export const axisTickStyle = { fill: CHART_COLORS.axisText, fontSize: 10 };
export const categoryTickStyle = { fill: CHART_COLORS.labelText, fontSize: 10 };

export const legendStyle = { fontSize: 11, fontFamily: "monospace" };
