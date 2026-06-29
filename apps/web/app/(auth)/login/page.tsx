"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("cfo@nimbus.test");
  const [password, setPassword] = useState("aurora-demo-2026");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/overview");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm rounded-lg border border-border bg-surface p-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold tracking-tight">AURORA</h1>
          <p className="text-sm text-text-muted">Enterprise Decision Intelligence OS</p>
        </div>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs text-text-muted">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-md border border-border bg-base px-3 py-2 text-sm outline-none focus:border-brand-accent"
              required
            />
          </div>
          <div>
            <label className="mb-1 block text-xs text-text-muted">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-md border border-border bg-base px-3 py-2 text-sm outline-none focus:border-brand-accent"
              required
            />
          </div>
          {error && <p className="text-sm text-negative">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-brand px-3 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="mt-4 text-xs text-text-muted">
          Demo: any seeded persona (ceo@, cfo@, coo@, … admin@nimbus.test)
        </p>
      </div>
    </main>
  );
}
