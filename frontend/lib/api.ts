const BASE = "/api";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export async function apiFetch(path: string, opts: RequestInit = {}) {
  const res = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...opts.headers },
    credentials: "include",
  });
  if (res.status === 401) {
    // try refresh
    const ref = await fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "include" });
    if (ref.ok) {
      const data = await ref.json();
      localStorage.setItem("access_token", data.access_token);
      // retry original
      return fetch(`${BASE}${path}`, {
        ...opts,
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${data.access_token}`, ...opts.headers },
        credentials: "include",
      });
    }
    localStorage.removeItem("access_token");
    window.location.href = "/login";
  }
  return res;
}

export function sseUrl(path: string): string {
  return `${BASE}${path}`;
}
