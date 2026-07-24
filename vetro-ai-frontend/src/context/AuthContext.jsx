import { createContext, useContext, useMemo, useState } from "react";

const STORAGE_KEY = "vetro_demo_officer";
const AuthContext = createContext(null);

const DEMO_USERS = {
  dgp_admin: { password: "demo123", name: "DGP Rao", role: "STATE_DGP", jurisdiction_type: "STATE", jurisdiction_id: "KARNATAKA" },
  sp_bengaluru: { password: "demo123", name: "SP Sharma", role: "DISTRICT_SP", jurisdiction_type: "DISTRICT", jurisdiction_id: "Bengaluru Urban" },
  sho_bengaluru: { password: "demo123", name: "Inspector Ravi", role: "STATION_OFFICER", jurisdiction_type: "STATION", jurisdiction_id: "Bengaluru Urban Town PS" },
};

function loadOfficer() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); } catch { return null; }
}

export function AuthProvider({ children }) {
  const [officer, setOfficer] = useState(loadOfficer);
  const login = (username, password) => {
    const candidate = DEMO_USERS[username];
    if (!candidate || candidate.password !== password) return false;
    const profile = { user_id: username, ...candidate };
    delete profile.password;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(profile));
    setOfficer(profile);
    return true;
  };
  const logout = () => { localStorage.removeItem(STORAGE_KEY); setOfficer(null); };
  const value = useMemo(() => ({ officer, isAuthenticated: Boolean(officer), login, logout }), [officer]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}

export function getStoredOfficer() { return loadOfficer(); }
