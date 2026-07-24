import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "../../context/AuthContext";

export default function Login() {
  const { isAuthenticated, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  if (isAuthenticated) return <Navigate to="/" replace />;
  function submit(event) {
    event.preventDefault();
    if (!login(username.trim(), password)) return setError("Invalid demo credentials.");
    navigate(location.state?.from?.pathname || "/", { replace: true });
  }
  return <main className="min-h-screen bg-[#0B1120] flex items-center justify-center p-6 text-[#E4E7EC]"><form onSubmit={submit} className="w-full max-w-md border border-[#2A3348] bg-[#151B2E] rounded-lg p-8 space-y-5"><div className="flex gap-3 items-center"><ShieldCheck className="text-[#D4A24C]" /><div><h1 className="font-mono text-lg">KSP Secure Access</h1><p className="text-xs text-[#8B93A8]">Vetro-AI demonstration login</p></div></div>{error && <p className="text-sm text-[#E06950]">{error}</p>}<input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Officer username" className="w-full rounded bg-[#0B1120] border border-[#2A3348] p-3" autoComplete="username" /><input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" type="password" className="w-full rounded bg-[#0B1120] border border-[#2A3348] p-3" autoComplete="current-password" /><button className="w-full rounded bg-[#D4A24C] text-[#0B1120] font-semibold p-3">Sign in</button><p className="text-xs text-[#6B7488]">Demo: dgp_admin, sp_bengaluru, or sho_bengaluru — password: demo123</p></form></main>;
}
