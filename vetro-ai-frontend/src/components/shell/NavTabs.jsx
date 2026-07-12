import { NavLink } from "react-router-dom";
import { Terminal, Share2, Map, TrendingUp, UserSearch } from "lucide-react";

const TABS = [
  { to: "/", label: "Chat", icon: Terminal, end: true },
  { to: "/network", label: "Network Graph", icon: Share2 },
  { to: "/map", label: "Hotspot Map", icon: Map },
  { to: "/trends", label: "Trends & Forecasting", icon: TrendingUp },
  { to: "/offenders", label: "Offender Profiling", icon: UserSearch },
];

export default function NavTabs() {
  return (
    <nav className="flex items-center gap-1 px-4 h-full">
      {TABS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `flex items-center gap-2 px-3 py-1.5 rounded text-xs font-mono uppercase tracking-wider
             transition-colors border-b-2 ${
               isActive
                 ? "text-accent border-accent"
                 : "text-ink-faint border-transparent hover:text-ink-secondary"
             }`
          }
        >
          <Icon className="w-3.5 h-3.5" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}
