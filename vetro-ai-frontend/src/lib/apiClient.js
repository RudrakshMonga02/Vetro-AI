import { getOwnerHeaders } from "./ownerToken";
import { getStoredOfficer } from "../context/AuthContext";

// Centralized base URL -- previously hardcoded and duplicated in both
// ChatApp.jsx and ChatInterface.jsx. Falls back to localhost for local
// dev; set VITE_API_BASE in a real deployment (see .env.example).
export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export function getOfficerHeaders() {
  const officer = getStoredOfficer();
  if (!officer) return {};
  return {
    "X-Officer-Id": officer.user_id,
    "X-Officer-Role": officer.role,
    "X-Officer-Jurisdiction-Type": officer.jurisdiction_type,
    "X-Officer-Jurisdiction-Id": officer.jurisdiction_id,
  };
}

const requestHeaders = (headers = {}) => ({ ...getOwnerHeaders(), ...getOfficerHeaders(), ...headers });

export async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, { headers: requestHeaders() });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}

export async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: requestHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}

export async function apiPatch(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: requestHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}

export async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: requestHeaders(),
  });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
}
