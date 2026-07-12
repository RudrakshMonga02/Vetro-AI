import { AUTH_HEADERS } from "./ownerToken";

// Centralized base URL -- previously hardcoded and duplicated in both
// ChatApp.jsx and ChatInterface.jsx. Falls back to localhost for local
// dev; set VITE_API_BASE in a real deployment (see .env.example).
export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`, { headers: AUTH_HEADERS });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}

export async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...AUTH_HEADERS },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}

export async function apiPatch(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...AUTH_HEADERS },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
  return res.json();
}

export async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "DELETE",
    headers: AUTH_HEADERS,
  });
  if (!res.ok) throw new Error(`Server returned ${res.status}`);
}
