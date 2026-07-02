"use client";

import { useCallback, useEffect, useState } from "react";
import {
  assignUserRole,
  formatMetricLabel,
  getMe,
  isForbiddenError,
  listAuditLogs,
  listRoles,
  listWorkspaceUsers,
  removeUserRole,
  type AuditLogEntry,
  type AuthUser,
  type RoleDefinition,
  type WorkspaceUser,
} from "@/lib/api";

type AdminTab = "users" | "audit";

function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function StatusPill({ active }: { active: boolean }) {
  return (
    <span
      className={`inline-flex rounded px-2 py-0.5 text-xs font-medium ${
        active ? "bg-positive/15 text-positive" : "bg-elevated text-text-muted"
      }`}
    >
      {active ? "Active" : "Inactive"}
    </span>
  );
}

function UsersTab({
  users,
  roles,
  canManage,
  onError,
  onUpdated,
}: {
  users: WorkspaceUser[];
  roles: RoleDefinition[];
  canManage: boolean;
  onError: (msg: string | null) => void;
  onUpdated: () => void;
}) {
  const [savingId, setSavingId] = useState<string | null>(null);
  // Holds unsaved edits only; the rendered value falls back to the user's
  // server-side role, so no effect is needed to mirror `users` into state.
  const [draftRoles, setDraftRoles] = useState<Record<string, string>>({});

  const onSaveRole = async (user: WorkspaceUser) => {
    const nextRole = draftRoles[user.id];
    if (!nextRole || nextRole === user.roles[0]) return;

    setSavingId(user.id);
    onError(null);
    try {
      if (user.roles[0]) {
        try {
          await removeUserRole(user.id, user.roles[0]);
        } catch {
          /* role removal may not exist yet */
        }
      }
      await assignUserRole(user.id, nextRole);
      onUpdated();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Failed to update role");
    } finally {
      setSavingId(null);
    }
  };

  if (!canManage) {
    return (
      <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-text-muted">
        You need the manage:users permission to view and edit workspace users.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-md border border-border">
      <table className="w-full text-sm">
        <thead className="bg-elevated text-left text-xs text-text-muted">
          <tr>
            <th className="px-3 py-2 font-medium">Name</th>
            <th className="px-3 py-2 font-medium">Email</th>
            <th className="px-3 py-2 font-medium">Title</th>
            <th className="px-3 py-2 font-medium">Role</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2 font-medium" />
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr key={user.id} className="border-t border-border/60">
              <td className="px-3 py-2.5 font-medium">{user.full_name}</td>
              <td className="px-3 py-2.5 text-text-muted">{user.email}</td>
              <td className="px-3 py-2.5 text-text-muted">{user.title}</td>
              <td className="px-3 py-2.5">
                <select
                  value={draftRoles[user.id] ?? user.roles[0] ?? ""}
                  onChange={(e) =>
                    setDraftRoles((prev) => ({ ...prev, [user.id]: e.target.value }))
                  }
                  className="w-full min-w-[10rem] rounded-md border border-border bg-elevated px-2 py-1 text-sm"
                >
                  <option value="">Select role…</option>
                  {roles.map((role) => (
                    <option key={role.name} value={role.name}>
                      {role.name}
                    </option>
                  ))}
                </select>
              </td>
              <td className="px-3 py-2.5">
                <StatusPill active={user.is_active} />
              </td>
              <td className="px-3 py-2.5 text-right">
                <button
                  type="button"
                  onClick={() => onSaveRole(user)}
                  disabled={
                    savingId === user.id ||
                    !draftRoles[user.id] ||
                    draftRoles[user.id] === user.roles[0]
                  }
                  className="rounded-md border border-border bg-surface px-2 py-1 text-xs font-medium hover:bg-elevated disabled:opacity-50"
                >
                  {savingId === user.id ? "Saving…" : "Save"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AuditTab({
  entries,
  loading,
  filters,
  onFiltersChange,
  onSearch,
  canView,
  pagination,
  onPageChange,
}: {
  entries: AuditLogEntry[];
  loading: boolean;
  filters: { action: string; resource_type: string; q: string };
  onFiltersChange: (patch: Partial<typeof filters>) => void;
  onSearch: () => void;
  canView: boolean;
  pagination: { page: number; total_pages: number; total_items: number };
  onPageChange: (page: number) => void;
}) {
  if (!canView) {
    return (
      <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-text-muted">
        You need the view:audit_log permission to browse the audit trail.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-4">
        <label className="block text-sm sm:col-span-2">
          <span className="text-text-muted">Search</span>
          <input
            type="search"
            value={filters.q}
            onChange={(e) => onFiltersChange({ q: e.target.value })}
            placeholder="User, resource, or action…"
            className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 text-sm"
          />
        </label>
        <label className="block text-sm">
          <span className="text-text-muted">Action</span>
          <input
            type="text"
            value={filters.action}
            onChange={(e) => onFiltersChange({ action: e.target.value })}
            placeholder="e.g. user.update"
            className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 text-sm"
          />
        </label>
        <label className="block text-sm">
          <span className="text-text-muted">Resource type</span>
          <input
            type="text"
            value={filters.resource_type}
            onChange={(e) => onFiltersChange({ resource_type: e.target.value })}
            placeholder="e.g. user"
            className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 text-sm"
          />
        </label>
      </div>
      <button
        type="button"
        onClick={onSearch}
        className="rounded-md border border-border bg-elevated px-3 py-1.5 text-xs font-medium hover:bg-surface"
      >
        Apply filters
      </button>

      <div className="overflow-hidden rounded-md border border-border">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-elevated text-left text-xs text-text-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Time</th>
              <th className="px-3 py-2 font-medium">Action</th>
              <th className="px-3 py-2 font-medium">Resource</th>
              <th className="px-3 py-2 font-medium">User</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-text-muted">
                  Loading audit events…
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-text-muted">
                  No audit events match your filters.
                </td>
              </tr>
            ) : (
              entries.map((entry) => (
                <tr key={entry.id} className="border-t border-border/60">
                  <td className="px-3 py-2.5 tabular-nums text-text-muted">
                    {formatTimestamp(entry.created_at)}
                  </td>
                  <td className="px-3 py-2.5 font-mono text-xs">{entry.action}</td>
                  <td className="px-3 py-2.5">
                    <span className="text-text-muted">{entry.resource_type}</span>
                    {entry.resource_id && (
                      <span className="ml-1 font-mono text-xs">{entry.resource_id.slice(0, 8)}…</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-text-muted">
                    {entry.user_email ?? entry.user_id ?? "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {pagination.total_pages > 1 && (
        <div className="flex items-center justify-between text-xs text-text-muted">
          <span>
            Page {pagination.page} of {pagination.total_pages} ({pagination.total_items} events)
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={pagination.page <= 1}
              onClick={() => onPageChange(pagination.page - 1)}
              className="rounded border border-border px-2 py-1 disabled:opacity-50"
            >
              Previous
            </button>
            <button
              type="button"
              disabled={pagination.page >= pagination.total_pages}
              onClick={() => onPageChange(pagination.page + 1)}
              className="rounded border border-border px-2 py-1 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AdminPage() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [tab, setTab] = useState<AdminTab>("users");
  const [forbidden, setForbidden] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [users, setUsers] = useState<WorkspaceUser[]>([]);
  const [roles, setRoles] = useState<RoleDefinition[]>([]);
  const [auditEntries, setAuditEntries] = useState<AuditLogEntry[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditPage, setAuditPage] = useState(1);
  const [auditPagination, setAuditPagination] = useState({
    page: 1,
    total_pages: 0,
    total_items: 0,
  });
  const [auditFilters, setAuditFilters] = useState({
    action: "",
    resource_type: "",
    q: "",
  });

  const canManageUsers = user?.permissions.includes("manage:users") ?? false;
  const canViewAudit = user?.permissions.includes("view:audit_log") ?? false;

  const loadUsers = useCallback(async () => {
    if (!canManageUsers) return;
    try {
      const [usersRes, rolesRes] = await Promise.all([
        listWorkspaceUsers(),
        listRoles().catch(() => [] as RoleDefinition[]),
      ]);
      setUsers(usersRes.data);
      setRoles(rolesRes);
      setForbidden(false);
    } catch (e) {
      if (isForbiddenError(e)) {
        setForbidden(true);
      } else {
        setError(e instanceof Error ? e.message : "Failed to load users");
      }
    }
  }, [canManageUsers]);

  const loadAudit = useCallback(
    async (page = auditPage) => {
      if (!canViewAudit) return;
      setAuditLoading(true);
      try {
        const res = await listAuditLogs({
          page,
          page_size: 25,
          action: auditFilters.action || undefined,
          resource_type: auditFilters.resource_type || undefined,
          q: auditFilters.q || undefined,
        });
        setAuditEntries(res.data);
        setAuditPagination({
          page: res.pagination.page,
          total_pages: res.pagination.total_pages,
          total_items: res.pagination.total_items,
        });
        setForbidden(false);
      } catch (e) {
        if (isForbiddenError(e)) {
          setForbidden(true);
        } else {
          setError(e instanceof Error ? e.message : "Failed to load audit log");
        }
      } finally {
        setAuditLoading(false);
      }
    },
    [auditFilters, auditPage, canViewAudit],
  );

  useEffect(() => {
    getMe()
      .then(setUser)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!user) return;
    if (canManageUsers) {
      Promise.resolve().then(loadUsers);
    } else if (canViewAudit) {
      Promise.resolve().then(() => setTab("audit"));
    }
  }, [user, canManageUsers, canViewAudit, loadUsers]);

  useEffect(() => {
    if (user && tab === "audit" && canViewAudit) {
      Promise.resolve().then(() => loadAudit(auditPage));
    }
  }, [user, tab, canViewAudit, auditPage, loadAudit]);

  const hasAnyAccess = canManageUsers || canViewAudit;

  if (loading) {
    return (
      <div className="p-8">
        <p className="text-sm text-text-muted">Loading admin console…</p>
      </div>
    );
  }

  if (forbidden || !hasAnyAccess) {
    return (
      <div className="p-8">
        <header className="mb-6">
          <h1 className="text-2xl font-bold tracking-tight">Admin</h1>
        </header>
        <div className="rounded-lg border border-border bg-surface px-6 py-10 text-center">
          <h2 className="text-lg font-semibold">Access restricted</h2>
          <p className="mt-2 text-sm text-text-muted">
            {forbidden
              ? "You don't have permission to access the admin console. Contact your workspace administrator."
              : "Admin features require manage:users or view:audit_log permissions."}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Admin</h1>
        <p className="text-sm text-text-muted">
          Manage workspace users, roles, and browse the audit trail.
        </p>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning">
          {error}
        </div>
      )}

      <div className="mb-4 flex gap-1 rounded-lg border border-border bg-elevated p-1">
        {canManageUsers && (
          <button
            type="button"
            onClick={() => setTab("users")}
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
              tab === "users"
                ? "bg-surface text-text-primary shadow-sm"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            Users
          </button>
        )}
        {canViewAudit && (
          <button
            type="button"
            onClick={() => setTab("audit")}
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition ${
              tab === "audit"
                ? "bg-surface text-text-primary shadow-sm"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            Audit log
          </button>
        )}
      </div>

      <section className="rounded-lg border border-border bg-surface p-5">
        {tab === "users" && canManageUsers && (
          <>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Workspace users</h2>
              <span className="text-xs text-text-muted">{users.length} users</span>
            </div>
            <UsersTab
              users={users}
              roles={roles}
              canManage={canManageUsers}
              onError={setError}
              onUpdated={loadUsers}
            />
          </>
        )}

        {tab === "audit" && canViewAudit && (
          <>
            <div className="mb-4">
              <h2 className="text-sm font-semibold">Audit log</h2>
              <p className="mt-1 text-xs text-text-muted">
                Filter by {formatMetricLabel("action")}, resource type, or free-text search.
              </p>
            </div>
            <AuditTab
              entries={auditEntries}
              loading={auditLoading}
              filters={auditFilters}
              onFiltersChange={(patch) => setAuditFilters((prev) => ({ ...prev, ...patch }))}
              onSearch={() => {
                setAuditPage(1);
                loadAudit(1);
              }}
              canView={canViewAudit}
              pagination={auditPagination}
              onPageChange={(page) => {
                setAuditPage(page);
                loadAudit(page);
              }}
            />
          </>
        )}
      </section>
    </div>
  );
}
