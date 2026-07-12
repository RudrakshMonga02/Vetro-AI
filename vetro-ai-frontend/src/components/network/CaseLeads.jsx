import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Sparkles, Lightbulb } from "lucide-react";
import { apiGet, apiPost } from "../../lib/apiClient";
import Panel from "../ui/Panel";
import LoadingState from "../ui/LoadingState";

/** Structural investigative leads for one case (cross-case accused links +
 * other open cases in the same district/crime type -- both purely
 * structural, no LLM), plus an optional button-triggered LLM synthesis
 * step. Mirrors OffenderDetail.jsx's "don't spend LLM quota
 * automatically" pattern: the structural leads always load, the summary
 * paragraph only generates on request. See GET /offenders/case/{id}/leads
 * and POST /offenders/case/{id}/leads/summarize. */
export default function CaseLeads({ caseId }) {
  const navigate = useNavigate();
  const [leads, setLeads] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [summary, setSummary] = useState(null);
  const [summaryError, setSummaryError] = useState(null);
  const [loadingSummary, setLoadingSummary] = useState(false);

  useEffect(() => {
    if (!caseId) return;
    setIsLoading(true);
    setLeads(null);
    setSummary(null);
    setSummaryError(null);
    apiGet(`/offenders/case/${caseId}/leads`)
      .then(setLeads)
      .catch(() => setLeads({ cross_case_links: [], similar_open_cases: [] }))
      .finally(() => setIsLoading(false));
  }, [caseId]);

  async function handleGenerateSummary() {
    setLoadingSummary(true);
    setSummaryError(null);
    try {
      const result = await apiPost(`/offenders/case/${caseId}/leads/summarize`);
      setSummary(result.leads_summary ?? "No clear leads could be generated from the available data.");
    } catch {
      setSummaryError("Not enough grounded data to generate a leads summary for this case.");
    } finally {
      setLoadingSummary(false);
    }
  }

  if (isLoading) return <LoadingState size="sm" fill={false} />;

  const hasCrossCase = leads?.cross_case_links?.length > 0;
  const hasSimilar = leads?.similar_open_cases?.length > 0;
  const hasFindings = hasCrossCase || hasSimilar;

  return (
    <Panel className="p-3">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-1.5">
          <Lightbulb className="w-3 h-3 text-ink-faint" />
          <span className="text-[10px] font-mono uppercase tracking-wider text-ink-faint">
            Suggested Leads
          </span>
        </div>
        {hasFindings && !summary && (
          <button
            onClick={handleGenerateSummary}
            disabled={loadingSummary}
            className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider
                       text-accent hover:text-accent-hover disabled:opacity-40"
          >
            {loadingSummary ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
            Generate Summary
          </button>
        )}
      </div>

      {summary && <p className="text-xs text-ink-secondary leading-relaxed mb-3">{summary}</p>}
      {summaryError && <p className="text-[11px] text-status-error mb-3">{summaryError}</p>}

      {!hasFindings && (
        <p className="text-[11px] text-ink-faint">No structural leads found for this case.</p>
      )}

      {hasCrossCase && (
        <div className="mb-3">
          <p className="text-[10px] font-mono uppercase text-ink-dim mb-1.5">
            Cross-case accused links
          </p>
          <div className="space-y-1.5">
            {leads.cross_case_links.map((c, i) => (
              <button
                key={i}
                onClick={() => navigate(`/network?case=${c.case_id}`)}
                className="w-full text-left text-[11px] text-ink-secondary hover:text-accent transition-colors"
              >
                {c.accused_name} &middot; Case {c.case_id} ({c.crime_type}, {c.district}, {c.date})
              </button>
            ))}
          </div>
        </div>
      )}

      {hasSimilar && (
        <div>
          <p className="text-[10px] font-mono uppercase text-ink-dim mb-1.5">
            Similar open cases nearby
          </p>
          <div className="space-y-1.5">
            {leads.similar_open_cases.map((c) => (
              <button
                key={c.case_id}
                onClick={() => navigate(`/network?case=${c.case_id}`)}
                className="w-full text-left text-[11px] text-ink-secondary hover:text-accent transition-colors"
              >
                Case {c.case_id} ({c.crime_type}, {c.district}, {c.date}) &middot; {c.status}
              </button>
            ))}
          </div>
        </div>
      )}
    </Panel>
  );
}
