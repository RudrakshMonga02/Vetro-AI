import { Loader2 } from "lucide-react";

/** Shared loading spinner block. `size` controls icon size for use in
 * both full-panel loading states and inline/small contexts. */
export default function LoadingState({ size = "md", fill = true }) {
  const iconSize = size === "sm" ? "w-4 h-4" : size === "lg" ? "w-6 h-6" : "w-5 h-5";
  return (
    <div className={`flex items-center justify-center ${fill ? "h-full" : "py-6"}`}>
      <Loader2 className={`${iconSize} animate-spin text-ink-dim`} />
    </div>
  );
}
