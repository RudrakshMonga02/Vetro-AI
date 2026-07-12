/**
 * The list-sidebar + detail-area layout NetworkGraphView and
 * OffenderProfilingView each hand-rolled separately. Also backs Hotspot
 * Map's case-list drill-down panel.
 */
export default function SplitPaneShell({ sidebar, sidebarWidth = "w-80", children }) {
  return (
    <div className="flex h-full">
      <div className={`${sidebarWidth} shrink-0 border-r border-line bg-surface-raised flex flex-col overflow-hidden`}>
        {sidebar}
      </div>
      <div className="flex-1 min-w-0 flex flex-col">{children}</div>
    </div>
  );
}
