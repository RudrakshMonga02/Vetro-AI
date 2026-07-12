/**
 * Shared empty-state block -- replaces the ~6 near-duplicate one-off
 * "no data yet" blocks that had drifted slightly different wording/
 * spacing across NetworkGraphView, HotspotMapView, TrendsView's
 * sub-components, and OffenderProfilingView.
 */
export default function EmptyState({ icon: Icon, title, hint }) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center px-4 gap-2">
      {Icon && <Icon className="w-5 h-5 text-ink-dim mb-1" />}
      {title && (
        <p className="font-mono text-xs text-ink-faint tracking-wide uppercase">{title}</p>
      )}
      {hint && <p className="text-sm text-ink-dim max-w-sm">{hint}</p>}
    </div>
  );
}
