import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Sparkles, GitBranch, Layers } from "lucide-react";
import { apiGet, apiPost } from "../../lib/apiClient";
import EmptyState from "../ui/EmptyState";
import Panel from "../ui/Panel";

/**
 * Shows one repeat offender's cases, with on-demand MO (modus operandi)
 * extraction per case -- deliberately NOT auto-fetched for every case
 * on mount. MO extraction is a real, billed Gemini call per case (see
 * api/services/mo_extraction.py); this project's Gemini free-tier quota
 * has already been exhausted once during dev, so this view only spends
 * that budget when an investigator actually asks for it. Same logic
 * applies to the combined profile synthesis below -- it only ever
 * combines summaries already fetched, never re-extracts anything.
 */
export default function OffenderDetail({ offender }) {
  const navigate = useNavigate();
  const [moByCaseId, setMoByCaseId] = useState({});
  const [loadingCaseId, setLoadingCaseId] = useState(null);
  const [profile, setProfile] = useState(null);
  const [loadingProfile, setLoadingProfile] = useState(false);

  async function loadMo(caseId) {
    setLoadingCaseId(caseId);
    try {
      const result = await apiGet(`/offenders/case/${caseId}/mo`);
      setMoByCaseId((prev) => ({ ...prev, [caseId]: result }));
    } catch {
      setMoByCaseId((prev) => ({
        ...prev,
        [caseId]: { mo_summary: null, keywords: [], error: "extraction_unavailable" },
      }));
    } finally {
      setLoadingCaseId(null);
    }
  }

  const extractedSummaries = Object.values(moByCaseId)
    .map((m) => m.mo_summary)
    .filter(Boolean);

  async function handleSynthesize() {
    setLoadingProfile(true);
    setProfile(null);
    try {
      const result = await apiPost("/offenders/synthesize-profile", { mo_summaries: extractedSummaries });
      setProfile(result.profile_summary ?? "No combined pattern could be determined.");
    } catch {
      setProfile("Profile synthesis unavailable right now.");
    } finally {
      setLoadingProfile(false);
    }
  }

  if (!offender) {
    return <EmptyState title="Select a repeat offender from the list" />;
  }

  return (
    <div className="h-full overflow-y-auto px-6 py-5">
      <div className="flex items-start justify-between gap-3 mb-1">
        <h2 className="font-mono text-sm text-ink-primary">{offender.accused_name}</h2>
        <button
          onClick={() => navigate(`/network?offender=${encodeURIComponent(offender.accused_name)}`)}
          className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider
                     text-accent hover:text-accent-hover shrink-0"
        >
          <GitBranch className="w-3 h-3" /> View Network
        </button>
      </div>
      <p className="text-[11px] text-ink-dim mb-5">
        {offender.case_count} linked cases &middot; name-matched, not verified identity
      </p>

      {extractedSummaries.length >= 2 && (
        <Panel className="p-3 mb-5">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-mono uppercase tracking-wider text-ink-faint">
              Combined Behavioral Profile
            </span>
            {!profile && (
              <button
                onClick={handleSynthesize}
                disabled={loadingProfile}
                className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider
                           text-accent hover:text-accent-hover disabled:opacity-40"
              >
                {loadingProfile ? <Loader2 className="w-3 h-3 animate-spin" /> : <Layers className="w-3 h-3" />}
                Synthesize Profile
              </button>
            )}
          </div>
          {profile && <p className="text-xs text-ink-secondary leading-relaxed mt-2">{profile}</p>}
        </Panel>
      )}

      <div className="space-y-3">
        {offender.cases.map((c) => {
          const mo = moByCaseId[c.case_id];
          const isLoadingThis = loadingCaseId === c.case_id;
          return (
            <Panel key={c.case_id} className="p-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs text-ink-primary font-mono">FIR {c.crime_no}</p>
                  <p className="text-[11px] text-ink-faint mt-0.5">
                    {c.district} &middot; {c.crime_type} &middot; {c.date}
                  </p>
                </div>
                {!mo && (
                  <button
                    onClick={() => loadMo(c.case_id)}
                    disabled={isLoadingThis}
                    className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider
                               text-accent hover:text-accent-hover disabled:opacity-40 shrink-0"
                  >
                    {isLoadingThis ? (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    ) : (
                      <Sparkles className="w-3 h-3" />
                    )}
                    Extract MO
                  </button>
                )}
              </div>
              {mo && (
                <div className="mt-2 pt-2 border-t border-line">
                  {mo.error ? (
                    <p className="text-[11px] text-status-error">MO extraction unavailable for this case.</p>
                  ) : (
                    <>
                      <p className="text-xs text-ink-secondary leading-snug">{mo.mo_summary}</p>
                      {mo.keywords?.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-2">
                          {mo.keywords.map((k) => (
                            <span
                              key={k}
                              className="text-[10px] font-mono text-ink-faint border border-line rounded px-1.5 py-0.5"
                            >
                              {k}
                            </span>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              )}
            </Panel>
          );
        })}
      </div>
    </div>
  );
}
