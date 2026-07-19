import { useState, useEffect, useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, Loader2 } from "lucide-react";
import { apiGet } from "../../lib/apiClient";
import OffenderDetail from "./OffenderDetail";
import EmptyState from "../ui/EmptyState";
import LoadingState from "../ui/LoadingState";
import SplitPaneShell from "../ui/SplitPaneShell";
import Badge from "../ui/Badge";

// Same thresholds as _risk_tier() in infrastructure/persistence/postgres_repository.py
// -- /offenders/{name}/cases (unlike /offenders/repeat) doesn't compute a
// risk tier server-side, since it's meant for "does this name have ANY
// cases at all," not the repeat-offender list. Replicated here rather
// than adding a field the repeat-offender endpoint doesn't need.
function riskTierFor(caseCount) {
  if (caseCount >= 5) return "high";
  if (caseCount >= 3) return "medium";
  return "low";
}

export default function OffenderProfilingView() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [offenders, setOffenders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const [minCaseCount, setMinCaseCount] = useState(2);

  const [searchInput, setSearchInput] = useState(searchParams.get("name") ?? "");
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState(null);

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

  // A search can surface a single-case offender who will never appear
  // in the repeat-offender list above (that list is filtered to
  // minCaseCount+ by construction) -- /offenders/{name}/cases supports
  // ANY accused name with at least one case, not just repeat offenders.
  const loadOffenderByName = useCallback(async (name) => {
    const result = await apiGet(`/offenders/${encodeURIComponent(name)}/cases`);
    const adapted = {
      accused_name: result.accused_name,
      case_count: result.match_count,
      risk_tier: riskTierFor(result.match_count),
      cases: result.cases,
    };
    setSelected(adapted);
    return adapted;
  }, []);

  // A numeric search input is treated as a Case ID -- look up its
  // accused via the existing /graph/case/{id} payload rather than a new
  // endpoint, then fall into the same by-name lookup above.
  async function lookupByCaseId(caseId) {
    const data = await apiGet(`/graph/case/${caseId}`);
    const accusedNodes = data.nodes.filter((n) => n.type === "accused");
    if (accusedNodes.length === 0) {
      throw new Error("No accused found for this case");
    }
    return accusedNodes[0].label;
  }

  async function handleSearchSubmit() {
    const query = searchInput.trim();
    if (!query) return;
    setSearchError(null);
    setSearching(true);
    try {
      if (/^\d+$/.test(query)) {
        const name = await lookupByCaseId(query);
        await loadOffenderByName(name);
        setSearchParams({ name });
        return;
      }
      // Instant local match first (no network round-trip) -- falls
      // through to the API lookup only if this name isn't in the
      // currently-loaded repeat-offender list (e.g. a single-case name,
      // or one below the current Min. cases threshold).
      const localMatch = offenders.find(
        (o) => o.accused_name.toLowerCase() === query.toLowerCase()
      );
      if (localMatch) {
        setSelected(localMatch);
        setSearchParams({ name: localMatch.accused_name });
        return;
      }
      const adapted = await loadOffenderByName(query);
      setSearchParams({ name: adapted.accused_name });
    } catch {
      setSearchError("No matching case or offender found.");
    } finally {
      setSearching(false);
    }
  }

  // Deep-linking: ?name=<accused name> (used by CaseGraph's accused-node
  // click) selects that offender directly, same pattern as
  // NetworkGraphView's ?case=/?offender= handling. Waits for the initial
  // repeat-offender fetch to settle first so a local match (no network
  // call) is preferred when available.
  useEffect(() => {
    const nameParam = searchParams.get("name");
    if (!nameParam || loading) return;
    // Already showing this offender -- skip. Without this, changing
    // minCaseCount (which toggles `loading` false->true->false and
    // re-fetches `offenders`) re-runs this effect and would redundantly
    // re-select/re-fetch the same name even though the URL never
    // changed, and could flicker a stale searchError.
    if (selected?.accused_name === nameParam) return;
    const localMatch = offenders.find((o) => o.accused_name === nameParam);
    if (localMatch) {
      setSearchError(null);
      setSelected(localMatch);
    } else {
      loadOffenderByName(nameParam)
        .then(() => setSearchError(null))
        .catch(() => setSearchError("No matching case or offender found."));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, loading]);

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
            <Search className="w-3.5 h-3.5 text-ink-faint shrink-0" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearchSubmit()}
              placeholder="Search name or Case ID..."
              className="flex-1 min-w-0 bg-transparent text-xs text-ink-primary placeholder-ink-dim
                         focus:outline-none font-mono"
            />
            {searching && <Loader2 className="w-3.5 h-3.5 text-ink-faint animate-spin shrink-0" />}
          </div>
          {searchError && (
            <p className="px-4 py-1.5 text-[11px] text-status-error border-b border-line">{searchError}</p>
          )}
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
                onClick={() => {
                  setSelected(o);
                  setSearchParams({ name: o.accused_name });
                }}
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
