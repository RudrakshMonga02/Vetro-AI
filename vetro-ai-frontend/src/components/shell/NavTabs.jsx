import { NavLink } from "react-router-dom";
import { Terminal, Share2, Map, TrendingUp, UserSearch, LogOut, ShieldCheck } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";

const TABS = [
  { to: "/", label: "Chat", icon: Terminal, end: true },
  { to: "/network", label: "Network Graph", icon: Share2 },
  { to: "/map", label: "Hotspot Map", icon: Map },
  { to: "/trends", label: "Trends & Forecasting", icon: TrendingUp },
  { to: "/offenders", label: "Offender Profiling", icon: UserSearch },
];

export default function NavTabs() {
  const { officer, logout } = useAuth(); const navigate = useNavigate();
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
      <div className="ml-auto flex items-center gap-3 text-xs font-mono">
        <span className="flex items-center gap-1 rounded border border-[#3A6B4C] px-2 py-1 text-[#B9D7BE]"><ShieldCheck className="w-3.5 h-3.5" /> Security Clearance: {officer.role} | {officer.jurisdiction_id}</span>
        <button onClick={() => { logout(); navigate("/login"); }} className="flex items-center gap-1 text-[#E06950] hover:text-[#FF8B75]"><LogOut className="w-3.5 h-3.5" /> Logout</button>
      </div>
    </nav>
  );
}
