import { Outlet } from "react-router-dom";
import NavTabs from "./NavTabs";

/**
 * Top-level shell: a slim nav bar + whichever tab is active below it.
 * The Chat tab ("/") keeps its own internal Sidebar + ChatInterface
 * split; the other four tabs are single full-height views. Every
 * child view should size itself with h-full, not h-screen, now that
 * the nav bar takes a slice of the viewport -- h-screen inside here
 * would overflow by the nav bar's height.
 */
export default function AppShell() {
  return (
    <div className="flex flex-col h-screen bg-surface-base">
      <header className="h-12 shrink-0 border-b border-line bg-surface-raised">
        <NavTabs />
      </header>
      <div className="flex-1 min-h-0">
        <Outlet />
      </div>
    </div>
  );
}
