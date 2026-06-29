/**
 * Minimal typed API client for the AURORA backend.
 *
 * Phase 1 hand-rolls a thin wrapper; Phase 2 replaces this with the generated client in
 * `packages/types` (OpenAPI -> TS), per docs/architecture/folder-structure.md.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost/api/v1";
const TOKEN_KEY = "aurora.access_token";

export type AuthUser = {
  id: string;
  full_name: string;
  email: string;
  title: string;
  company: { id: string; name: string; slug: string };
  roles: string[];
  permissions: string[];
};

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      message = body?.error?.message ?? message;
    } catch {
      /* non-JSON error */
    }
    throw new Error(message);
  }
  return (await res.json()) as T;
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const data = await request<{ access_token: string; user: AuthUser }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(data.access_token);
  return data.user;
}

export async function getMe(): Promise<AuthUser> {
  return request<AuthUser>("/auth/me");
}
