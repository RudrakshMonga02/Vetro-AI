/**
 * Generalized pill badge -- replaces the risk-tier color maps that had
 * drifted slightly different values between NetworkGraphView and
 * OffenderProfilingView, and covers status/match-basis badges too
 * (citation case-number chips, "name-matched" caveats, etc.).
 */
const TONES = {
  high: "text-status-error border-status-error bg-status-error/10",
  medium: "text-accent border-accent bg-accent/10",
  low: "text-ink-faint border-line",
  neutral: "text-ink-faint border-line",
  info: "text-ink-muted border-line",
};

export default function Badge({ tone = "neutral", children, title, className = "" }) {
  return (
    <span
      title={title}
      className={`inline-flex items-center text-[9px] font-mono uppercase tracking-wide
                  border rounded px-1.5 py-0.5 shrink-0 ${TONES[tone] ?? TONES.neutral} ${className}`}
    >
      {children}
    </span>
  );
}
