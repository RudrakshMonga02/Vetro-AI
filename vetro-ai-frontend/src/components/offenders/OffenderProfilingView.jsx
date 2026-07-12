import { useState, useEffect } from "react";
import { apiGet } from "../../lib/apiClient";
import OffenderDetail from "./OffenderDetail";
import EmptyState from "../ui/EmptyState";
import LoadingState from "../ui/LoadingState";
import SplitPaneShell from "../ui/SplitPaneShell";
import Badge from "../ui/Badge";

export default function OffenderProfilingView() {
  const [offenders, setOffenders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [minCaseCount, setMinCaseCount] = useState(2);

  useEffect(() => {
    setLoading(true);
    apiGet(`/offenders/repeat?min_case_count=${minCaseCount}`)
      .then((data) => {
        setOffenders(data);
        setSelected((prev) => data.find((o) => o.accused_name === prev?.accused_name) ?? data[0] ?? null);
      })
      .catch((err) => console.error("Failed to load offenders:", err))
      .finally(() => setLoading(false));
  }, [minCaseCount]);

  return (
    <SplitPaneShell
      sidebarWidth="w-96"
      sidebar={
        <>
          <div className="px-4 py-3 border-b border-line">
            <h2 className="font-mono text-xs uppercase tracking-wider text-accent">
              Offender Profiling
            </h2>
            <p className="text-[11px] text-ink-dim mt-1">
              Repeat-offender scoring — count-based, no ML. Name-matched
              across cases, not verified identity.
            </p>
          </div>
          <div className="px-4 py-2 border-b border-line flex items-center gap-2">
            <span className="text-[10px] font-mono uppercase text-ink-faint">Min. cases</span>
            <select
              value={minCaseCount}
              onChange={(e) => setMinCaseCount(Number(e.target.value))}
              className="bg-surface-panel border border-line rounded px-2 py-1 text-xs text-ink-secondary
                         font-mono focus:outline-none focus:border-accent"
            >
              {[2, 3, 4, 5].map((n) => (
                <option key={n} value={n}>{n}+</option>
              ))}
            </select>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading && <LoadingState size="sm" fill={false} />}
            {!loading && offenders.length === 0 && (
              <EmptyState title="No offenders meet this threshold" />
            )}
            {offenders.map((o) => (
              <button
                key={o.accused_name}
                onClick={() => setSelected(o)}
                className={`w-full text-left px-4 py-3 border-l-2 transition-colors hover:bg-surface-panel/60 ${
                  selected?.accused_name === o.accused_name
                    ? "bg-surface-panel border-accent"
                    : "border-transparent"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-ink-primary truncate">{o.accused_name}</span>
                  <Badge tone={o.risk_tier}>{o.risk_tier}</Badge>
                </div>
                <p className="text-[10px] text-ink-dim font-mono mt-1">
                  {o.case_count} cases &middot; {[...new Set(o.cases.map((c) => c.district))].slice(0, 2).join(", ")}
                </p>
              </button>
            ))}
          </div>
        </>
      }
    >
      <OffenderDetail offender={selected} />
    </SplitPaneShell>
  );
}
