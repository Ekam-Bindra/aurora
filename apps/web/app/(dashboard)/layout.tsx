"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { ExplainProvider } from "@/components/explain/ExplainProvider";
import { clearToken, getMe, getToken, type AuthUser } from "@/lib/api";

type NavItem = {
  href: string;
  label: string;
  permission: string | null;
  permissions?: string[];
  ready: boolean;
};

const NAV: NavItem[] = [
  { href: "/overview", label: "Overview", permission: null, ready: true },
  { href: "/financials", label: "Financials", permission: "read:financials", ready: true },
  { href: "/forecasting", label: "Forecasting", permission: "read:financials", ready: true },
  { href: "/risk", label: "Risk Genome", permission: "read:operations", ready: true },
  { href: "/graph", label: "Knowledge Graph", permission: "read:graph", ready: true },
  { href: "/simulations", label: "Simulations", permission: "run:simulation", ready: true },
  { href: "/agent", label: "AI Agent", permission: "use:ai_agent", ready: true },
  { href: "/reports", label: "Board Reports", permission: "create:board_report", ready: true },
  { href: "/data", label: "Data Sources", permission: "manage:data_sources", ready: true },
  {
    href: "/admin",
    label: "Admin",
    permission: null,
    permissions: ["manage:users", "view:audit_log"],
    ready: true,
  },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => {
        clearToken();
        router.replace("/login");
      });
  }, [router]);

  function onLogout() {
    clearToken();
    router.replace("/login");
  }

  const canSee = (item: NavItem) => {
    if (item.permissions?.length) {
      return item.permissions.some((p) => user?.permissions.includes(p));
    }
    return item.permission === null || (user?.permissions.includes(item.permission) ?? false);
  };

  return (
    <ExplainProvider>
    <div className="flex min-h-screen">
      <aside className="flex w-60 flex-col border-r border-border bg-surface">
        <div className="px-5 py-5">
          <div className="text-lg font-bold tracking-tight">AURORA</div>
          <div className="text-xs text-text-muted">{user?.company.name ?? "…"}</div>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV.filter(canSee).map((item) => {
            const active = pathname === item.href;
            const base = "block rounded-md px-3 py-2 text-sm transition";
            if (!item.ready) {
              return (
                <span
                  key={item.href}
                  className={`${base} cursor-default text-text-muted/60`}
                  title="Coming in a later phase"
                >
                  {item.label}
                  <span className="ml-2 rounded bg-elevated px-1.5 py-0.5 text-[10px]">soon</span>
                </span>
              );
            }
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`${base} ${active ? "bg-elevated text-text-primary" : "text-text-muted hover:bg-elevated hover:text-text-primary"}`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <div className="border-t border-border px-5 py-4">
          <div className="text-sm">{user?.full_name ?? "…"}</div>
          <div className="text-xs text-text-muted">{user?.title}</div>
          <button
            onClick={onLogout}
            className="mt-2 text-xs text-brand-accent hover:underline"
          >
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-auto">{children}</main>
    </div>
    </ExplainProvider>
  );
}
