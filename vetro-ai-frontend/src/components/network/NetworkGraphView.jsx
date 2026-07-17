import { useState, useEffect, useMemo, useCallback, useRef } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, Share2, GitBranch, Route, Sparkles, Loader2 } from "lucide-react";
import { apiGet } from "../../lib/apiClient";
import CaseGraph from "./CaseGraph";
import CaseTimeline from "./CaseTimeline";
import CaseLeads from "./CaseLeads";
import EmptyState from "../ui/EmptyState";
import LoadingState from "../ui/LoadingState";
import ErrorState from "../ui/ErrorState";
import SplitPaneShell from "../ui/SplitPaneShell";
import Badge from "../ui/Badge";

/** Aggregate multi-offender graph, derived entirely client-side from
 * the already-fetched /offenders/repeat response -- no new backend
 * endpoint. Nodes = offenders + the cases they appear in; a same-case
 * edge is drawn between two different offenders who are co-accused in
 * the same case_id (a real organized-crime-adjacent signal), WEIGHTED
 * by how many different cases the same pair shares -- an established
 * pairing across 3 cases should read very differently from a one-off
 * co-arrest, not as 3 overlapping identical lines. */
function buildAggregateGraph(offenders) {
  const nodes = new Map();
  const caseEdges = [];
  const caseToOffenders = new Map();

  for (const o of offenders) {
    const offenderId = `offender_${o.accused_name}`;
    nodes.set(offenderId, { id: offenderId, label: o.accused_name, type: "accused" });
    for (const c of o.cases) {
      const caseId = `case_${c.case_id}`;
      if (!nodes.has(caseId)) {
        nodes.set(caseId, { id: caseId, label: `Case ${c.case_id}`, type: "case" });
      }
      caseEdges.push({ source: offenderId, target: caseId, type: "appears-in" });
      if (!caseToOffenders.has(c.case_id)) caseToOffenders.set(c.case_id, []);
      caseToOffenders.get(c.case_id).push(offenderId);
    }
  }

  const edgeWeights = new Map(); // "idA|idB" (sorted) -> shared-case count
  for (const offenderIds of caseToOffenders.values()) {
    for (let i = 0; i < offenderIds.length; i++) {
      for (let j = i + 1; j < offenderIds.length; j++) {
        const key = [offenderIds[i], offenderIds[j]].sort().join("|");
        edgeWeights.set(key, (edgeWeights.get(key) ?? 0) + 1);
      }
    }
  }
  const coAccusedEdges = Array.from(edgeWeights.entries()).map(([key, weight]) => {
    const [source, target] = key.split("|");
    return { source, target, weight, type: "co-accused" };
  });

  return { nodes: Array.from(nodes.values()), edges: [...caseEdges, ...coAccusedEdges] };
}

export default function NetworkGraphView() {
  const [searchParams, setSearchParams] = useSearchParams();

  const [mode, setMode] = useState("single"); // "single" | "aggregate"
  const [caseIdInput, setCaseIdInput] = useState(searchParams.get("case") ?? "");
  const [graph, setGraph] = useState(null);
  const [graphError, setGraphError] = useState(null);
  const [loadingGraph, setLoadingGraph] = useState(false);
  const [selectedNode, setSelectedNode] = useState(null);
  const [loadedCaseId, setLoadedCaseId] = useState(null);

  const [repeatOffenders, setRepeatOffenders] = useState([]);
  const [loadingOffenders, setLoadingOffenders] = useState(true);
  const [selectedOffender, setSelectedOffender] = useState(null);

  // Path-finding (aggregate mode) -- operates on the live Cytoscape
  // instance via cy.elements().dijkstra(), not a new backend endpoint;
  // the aggregate graph is already fully loaded client-side.
  const cyInstanceRef = useRef(null);
  const [pathFrom, setPathFrom] = useState("");
  const [pathTo, setPathTo] = useState("");
  const [pathMessage, setPathMessage] = useState(null);

  // Similar-MO cases (single-case mode) -- merged into the currently
  // loaded graph's nodes/edges rather than a full reload.
  const [loadingSimilarMo, setLoadingSimilarMo] = useState(false);
  const [similarMoStatus, setSimilarMoStatus] = useState(null); // null | "done" | "empty" | "error"

  const loadCase = useCallback(async (caseId) => {
    if (!caseId) return;
    setLoadingGraph(true);
    setGraphError(null);
    setSelectedNode(null);
    setSimilarMoStatus(null);
    try {
      const data = await apiGet(`/graph/case/${caseId}`);
      setGraph(data);
      setLoadedCaseId(caseId);
    } catch {
      setGraph(null);
      setLoadedCaseId(null);
      setGraphError(`Case ${caseId} not found or has no linked records.`);
    } finally {
      setLoadingGraph(false);
    }
  }, []);

  useEffect(() => {
    apiGet("/offenders/repeat?min_case_count=2")
      .then(setRepeatOffenders)
      .catch((err) => console.error("Failed to load repeat offenders:", err))
      .finally(() => setLoadingOffenders(false));
  }, []);

  // Deep-linking: ?case=<id> loads that case directly (used by citation
  // badges in Chat, the Hotspot Map case-list drill-down, and now
  // CaseGraph's own accused-node click within a case); ?offender=
  // switches into aggregate mode with that offender pre-selected (used
  // by Offender Profiling's "View Network" button).
  useEffect(() => {
    const caseParam = searchParams.get("case");
    const offenderParam = searchParams.get("offender");
    if (caseParam) {
      setMode("single");
      setCaseIdInput(caseParam);
      loadCase(caseParam);
    } else if (offenderParam && repeatOffenders.length > 0) {
      const match = repeatOffenders.find((o) => o.accused_name === offenderParam);
      if (match) {
        setMode("aggregate");
        setSelectedOffender(match);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, repeatOffenders.length]);

  const aggregateGraph = useMemo(() => buildAggregateGraph(repeatOffenders), [repeatOffenders]);

  function handleSelectOffender(offender) {
    setSelectedOffender(offender);
    setSearchParams({ offender: offender.accused_name });
  }

  function handleModeChange(next) {
    setMode(next);
    setSelectedNode(null);
    setPathMessage(null);
    if (next === "single") setSearchParams(caseIdInput ? { case: caseIdInput } : {});
    else setSearchParams(selectedOffender ? { offender: selectedOffender.accused_name } : {});
  }

  function handleSearchSubmit() {
    setSearchParams({ case: caseIdInput });
    loadCase(caseIdInput);
  }

  function handleFindPath() {
    const cy = cyInstanceRef.current;
    if (!cy || !pathFrom.trim() || !pathTo.trim()) return;
    cy.elements().removeClass("path-highlight");

    const fromNode = cy.getElementById(`offender_${pathFrom.trim()}`);
    const toNode = cy.getElementById(`offender_${pathTo.trim()}`);
    if (fromNode.empty() || toNode.empty()) {
      setPathMessage("Enter two exact offender names from the list on the left.");
      return;
    }
    if (fromNode.id() === toNode.id()) {
      setPathMessage("Enter two different names.");
      return;
    }

    const dijkstra = cy.elements().dijkstra({ root: fromNode, directed: false });
    const path = dijkstra.pathTo(toNode);
    if (!path || path.length === 0) {
      setPathMessage("No connection found between these two.");
      return;
    }
    path.addClass("path-highlight");
    const hops = (path.length - 1) / 2;
    setPathMessage(`Connected — ${hops} hop${hops === 1 ? "" : "s"} apart.`);
  }

  async function handleFindSimilarMo() {
    if (!loadedCaseId) return;
    setLoadingSimilarMo(true);
    setSimilarMoStatus(null);
    try {
      const result = await apiGet(`/offenders/case/${loadedCaseId}/similar-mo`);
      if (!result.similar_cases || result.similar_cases.length === 0) {
        setSimilarMoStatus("empty");
        return;
      }
      setGraph((prev) => {
        if (!prev) return prev;
        const existingIds = new Set(prev.nodes.map((n) => n.id));
        const newNodes = [];
        const newEdges = [];
        for (const c of result.similar_cases) {
          const nodeId = `case_${c.case_id}`;
          if (!existingIds.has(nodeId)) {
            newNodes.push({ id: nodeId, label: `Case ${c.case_id}`, type: "case", similar_mo: true });
          }
          newEdges.push({
            source: `case_${loadedCaseId}`,
            target: nodeId,
            type: "similar-mo",
            label: `${c.shared_keywords.length} shared`,
          });
        }
        return { ...prev, nodes: [...prev.nodes, ...newNodes], edges: [...prev.edges, ...newEdges] };
      });
      setSimilarMoStatus("done");
    } catch {
      setSimilarMoStatus("error");
    } finally {
      setLoadingSimilarMo(false);
    }
  }

  const activeGraph = mode === "single" ? graph : aggregateGraph;

  return (
    <SplitPaneShell
      sidebar={
        <>
          <div className="px-4 py-3 border-b border-line">
            <h2 className="font-mono text-xs uppercase tracking-wider text-accent">
              Network Graph
            </h2>
            <div className="flex gap-1 mt-3">
              <button
                onClick={() => handleModeChange("single")}
                className={`flex-1 flex items-center justify-center gap-1.5 text-[10px] font-mono uppercase
                            tracking-wider px-2 py-1.5 rounded border transition-colors ${
                  mode === "single" ? "border-accent text-accent" : "border-line text-ink-faint hover:text-ink-secondary"
                }`}
              >
                <Share2 className="w-3 h-3" /> Single Case
              </button>
              <button
                onClick={() => handleModeChange("aggregate")}
                className={`flex-1 flex items-center justify-center gap-1.5 text-[10px] font-mono uppercase
                            tracking-wider px-2 py-1.5 rounded border transition-colors ${
                  mode === "aggregate" ? "border-accent text-accent" : "border-line text-ink-faint hover:text-ink-secondary"
                }`}
              >
                <GitBranch className="w-3 h-3" /> Offender Network
              </button>
            </div>
            <p className="text-[11px] text-ink-faint mt-2 leading-snug">
              {mode === "single"
                ? "One case's victim/accused/arrest links. Hover a person for a quick summary, click an accused for their full profile."
                : "All repeat offenders and the cases connecting them. Name-matched, not verified identity."}
            </p>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loadingOffenders && <LoadingState size="sm" fill={false} />}
            {!loadingOffenders && repeatOffenders.length === 0 && (
              <EmptyState title="No repeat offenders found" />
            )}
            {repeatOffenders.map((o) => (
              <button
                key={o.accused_name}
                onClick={() => handleSelectOffender(o)}
                className={`w-full text-left px-4 py-2.5 border-l-2 transition-colors hover:bg-surface-panel/60 ${
                  selectedOffender?.accused_name === o.accused_name
                    ? "bg-surface-panel border-accent"
                    : "border-transparent"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs text-ink-primary truncate">{o.accused_name}</span>
                  <Badge tone={o.risk_tier}>{o.risk_tier}</Badge>
                </div>
                <p className="text-[10px] text-ink-dim font-mono mt-0.5">{o.case_count} cases</p>
              </button>
            ))}
          </div>
        </>
      }
    >
      {mode === "single" && (
        <div className="px-6 py-3 border-b border-line flex items-center gap-3">
          <Search className="w-4 h-4 text-ink-faint shrink-0" />
          <input
            value={caseIdInput}
            onChange={(e) => setCaseIdInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearchSubmit()}
            placeholder="Enter a Case ID to view its network..."
            className="flex-1 bg-transparent text-sm text-ink-primary placeholder-ink-dim
                       focus:outline-none font-mono"
          />
          <button
            onClick={handleSearchSubmit}
            className="text-xs font-mono uppercase tracking-wider text-accent hover:text-accent-hover"
          >
            Load
          </button>
        </div>
      )}
      {mode === "aggregate" && (
        <div className="px-6 py-3 border-b border-line flex items-center gap-3">
          <Route className="w-4 h-4 text-ink-faint shrink-0" />
          <input
            value={pathFrom}
            onChange={(e) => setPathFrom(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleFindPath()}
            placeholder="Person A"
            list="offender-names"
            className="w-48 bg-transparent text-sm text-ink-primary placeholder-ink-dim
                       focus:outline-none font-mono"
          />
          <span className="text-ink-dim text-xs">&rarr;</span>
          <input
            value={pathTo}
            onChange={(e) => setPathTo(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleFindPath()}
            placeholder="Person B"
            list="offender-names"
            className="w-48 bg-transparent text-sm text-ink-primary placeholder-ink-dim
                       focus:outline-none font-mono"
          />
          <datalist id="offender-names">
            {repeatOffenders.map((o) => (
              <option key={o.accused_name} value={o.accused_name} />
            ))}
          </datalist>
          <button
            onClick={handleFindPath}
            className="text-xs font-mono uppercase tracking-wider text-accent hover:text-accent-hover shrink-0"
          >
            Find Path
          </button>
          {pathMessage && (
            <span className="text-[11px] text-ink-faint font-mono truncate">{pathMessage}</span>
          )}
        </div>
      )}
      <div className="flex-1 min-h-0 flex">
        <div className="flex-1 min-w-0 relative">
          {mode === "single" && loadingGraph && (
            <div className="absolute inset-0 bg-surface-base/60 z-10"><LoadingState /></div>
          )}
          {mode === "single" && graphError && !loadingGraph && <ErrorState message={graphError} />}
          {mode === "single" && !graph && !graphError && !loadingGraph && (
            <EmptyState
              title="No case loaded"
              hint="Select a repeat offender, or enter a Case ID above."
            />
          )}
          {mode === "aggregate" && repeatOffenders.length === 0 && !loadingOffenders && (
            <EmptyState title="No repeat-offender network to show" />
          )}
          {activeGraph && (mode === "single" ? !graphError : true) && (
            <CaseGraph
              graph={activeGraph}
              onNodeClick={setSelectedNode}
              onCyReady={(cy) => {
                cyInstanceRef.current = cy;
              }}
            />
          )}
        </div>
        {(selectedNode || (mode === "single" && loadedCaseId)) && (
          <div className="w-72 shrink-0 border-l border-line bg-surface-raised p-4 overflow-y-auto space-y-4">
            {selectedNode && (
              <div>
                <p className="text-[10px] font-mono uppercase tracking-wider text-ink-dim">
                  {selectedNode.type?.replace("_", " ")}
                </p>
                <p className="text-sm text-ink-primary mt-1">{selectedNode.label}</p>
                {(selectedNode.age !== undefined || selectedNode.gender !== undefined) && (
                  <p className="text-xs text-ink-faint font-mono mt-2">
                    {selectedNode.age != null && `Age ${selectedNode.age}`}
                    {selectedNode.age != null && selectedNode.gender != null && " · "}
                    {selectedNode.gender}
                  </p>
                )}
              </div>
            )}
            {mode === "single" && loadedCaseId && (
              <>
                <div className="border border-line rounded p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-mono uppercase tracking-wider text-ink-faint">
                      Similar-MO Cases
                    </span>
                    {similarMoStatus !== "done" && (
                      <button
                        onClick={handleFindSimilarMo}
                        disabled={loadingSimilarMo}
                        className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider
                                   text-accent hover:text-accent-hover disabled:opacity-40"
                      >
                        {loadingSimilarMo ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Sparkles className="w-3 h-3" />
                        )}
                        Find Similar-MO Cases
                      </button>
                    )}
                  </div>
                  {similarMoStatus === "done" && (
                    <p className="text-[11px] text-ink-secondary mt-2">
                      Added to the graph above (dotted purple).
                    </p>
                  )}
                  {similarMoStatus === "empty" && (
                    <p className="text-[11px] text-ink-faint mt-2">
                      No other case with the same crime type and an already-extracted MO shares
                      enough keywords with this one.
                    </p>
                  )}
                  {similarMoStatus === "error" && (
                    <p className="text-[11px] text-status-error mt-2">
                      Similar-MO lookup unavailable right now.
                    </p>
                  )}
                </div>
                <CaseTimeline caseId={loadedCaseId} />
                <CaseLeads caseId={loadedCaseId} />
              </>
            )}
          </div>
        )}
      </div>
    </SplitPaneShell>
  );
}
