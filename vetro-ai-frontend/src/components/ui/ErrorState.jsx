import { AlertTriangle } from "lucide-react";

/** Shared error block -- consistent styling for "this request failed"
 * states across every tab, distinct from EmptyState's neutral tone. */
export default function ErrorState({ message }) {
  return (
    <div className="h-full flex flex-col items-center justify-center gap-2 text-ink-faint px-4 text-center">
      <AlertTriangle className="w-5 h-5 text-status-error" />
      <p className="text-sm font-mono">{message}</p>
    </div>
  );
}
