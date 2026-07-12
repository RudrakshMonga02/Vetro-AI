import { useState, useEffect } from "react";
import { Clock } from "lucide-react";
import { apiGet } from "../../lib/apiClient";
import Panel from "../ui/Panel";
import LoadingState from "../ui/LoadingState";

/** Simple vertical timeline for one case's dated events, fetched from
 * GET /graph/case/{id}/timeline (see get_case_timeline() in
 * postgres_repository.py) -- events are already chronologically sorted
 * server-side. */
export default function CaseTimeline({ caseId }) {
  const [events, setEvents] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!caseId) return;
    setIsLoading(true);
    setError(null);
    apiGet(`/graph/case/${caseId}/timeline`)
      .then(setEvents)
      .catch(() => setError("Timeline unavailable for this case."))
      .finally(() => setIsLoading(false));
  }, [caseId]);

  if (isLoading) return <LoadingState size="sm" fill={false} />;
  if (error) return <p className="text-[11px] text-status-error px-3 py-2">{error}</p>;
  if (!events || events.length === 0) {
    return <p className="text-[11px] text-ink-faint px-3 py-2">No dated events on record for this case.</p>;
  }

  return (
    <Panel className="p-3">
      <div className="flex items-center gap-1.5 mb-3">
        <Clock className="w-3 h-3 text-ink-faint" />
        <span className="text-[10px] font-mono uppercase tracking-wider text-ink-faint">
          Investigation Timeline
        </span>
      </div>
      <ol className="space-y-3">
        {events.map((e, i) => (
          <li key={i} className="flex gap-3">
            <div className="flex flex-col items-center shrink-0 pt-0.5">
              <span className="w-2 h-2 rounded-full bg-accent" />
              {i < events.length - 1 && <span className="w-px flex-1 bg-line mt-1" />}
            </div>
            <div className="pb-1">
              <p className="text-xs text-ink-secondary">{e.label}</p>
              <p className="text-[10px] text-ink-dim font-mono mt-0.5">{e.date}</p>
            </div>
          </li>
        ))}
      </ol>
    </Panel>
  );
}
