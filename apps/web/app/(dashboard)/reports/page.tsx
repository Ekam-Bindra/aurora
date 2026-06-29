"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  approveBoardReport,
  boardReportStatusTone,
  BOARD_REPORT_SECTIONS,
  BOARD_REPORT_TEMPLATES,
  createBoardReport,
  formatBoardReportSection,
  generateBoardReport,
  getBoardReport,
  getBoardReportExport,
  getMe,
  listBoardReports,
  type AuthUser,
  type BoardReportDetail,
  type BoardReportSection,
  type BoardReportSummary,
  type BoardReportTemplate,
} from "@/lib/api";

function StatusBadge({
  label,
  tone,
}: {
  label: string;
  tone: "positive" | "warning" | "negative" | "muted";
}) {
  const bg =
    tone === "positive"
      ? "bg-positive/15 text-positive"
      : tone === "warning"
        ? "bg-warning/15 text-warning"
        : tone === "negative"
          ? "bg-negative/15 text-negative"
          : "bg-elevated text-text-muted";
  return (
    <span className={`inline-flex rounded px-2 py-0.5 text-xs font-medium capitalize ${bg}`}>
      {label.replace(/_/g, " ")}
    </span>
  );
}

function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function defaultPeriod(): { start: string; end: string } {
  const now = new Date();
  const end = new Date(now.getFullYear(), now.getMonth(), 0);
  const start = new Date(end.getFullYear(), end.getMonth() - 2, 1);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { start: fmt(start), end: fmt(end) };
}

function ReportRow({
  report,
  selected,
  onSelect,
}: {
  report: BoardReportSummary;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const tone = boardReportStatusTone(report.status);
  return (
    <button
      type="button"
      onClick={() => onSelect(report.id)}
      className={`w-full border-t border-border/60 px-3 py-2.5 text-left text-sm transition first:border-t-0 ${
        selected ? "bg-elevated" : "hover:bg-elevated/60"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">{report.title}</span>
        <StatusBadge label={report.status} tone={tone} />
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-text-muted">
        <span>
          {report.period_start} → {report.period_end}
        </span>
        <span>{report.sections.length} sections</span>
      </div>
    </button>
  );
}

function ReportDetailPanel({
  report,
  user,
  onRefresh,
  onApprove,
  approving,
}: {
  report: BoardReportDetail;
  user: AuthUser | null;
  onRefresh: () => void;
  onApprove: () => void;
  approving: boolean;
}) {
  const tone = boardReportStatusTone(report.status);
  const canApprove = user?.permissions.includes("approve:board_report") ?? false;
  const canDownload =
    report.status === "ready" ||
    report.status === "approved" ||
    report.status === "published" ||
    Boolean(report.export_url);

  const onDownload = async () => {
    try {
      const exp = await getBoardReportExport(report.id);
      window.open(exp.export_url, "_blank", "noopener,noreferrer");
    } catch {
      if (report.export_url) {
        window.open(report.export_url, "_blank", "noopener,noreferrer");
      }
    }
  };

  return (
    <div className="mt-4 rounded-md border border-border bg-elevated p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{report.title}</h3>
        <StatusBadge label={report.status} tone={tone} />
      </div>

      <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-text-muted">Period</dt>
          <dd>
            {report.period_start} → {report.period_end}
          </dd>
        </div>
        <div>
          <dt className="text-text-muted">Template</dt>
          <dd className="capitalize">{report.template?.replace(/_/g, " ") ?? "Standard"}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Created</dt>
          <dd>{formatTimestamp(report.created_at)}</dd>
        </div>
        <div>
          <dt className="text-text-muted">Generated</dt>
          <dd>{formatTimestamp(report.generated_at)}</dd>
        </div>
      </dl>

      <div className="mt-4">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Sections</h4>
        <ul className="mt-2 space-y-1">
          {report.sections.map((section) => (
            <li key={section} className="flex items-center gap-2 text-sm">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-accent" />
              {formatBoardReportSection(section)}
            </li>
          ))}
        </ul>
      </div>

      {report.metadata && Object.keys(report.metadata).length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            Report metadata
          </h4>
          <dl className="mt-2 grid gap-1 text-xs sm:grid-cols-2">
            {Object.entries(report.metadata).map(([key, value]) => (
              <div key={key} className="flex justify-between gap-2 rounded border border-border bg-surface px-2 py-1.5">
                <dt className="text-text-muted">{formatBoardReportSection(key)}</dt>
                <dd className="font-medium tabular-nums">{String(value)}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}

      {report.narrative && Object.keys(report.narrative).length > 0 && (
        <div className="mt-4 space-y-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Preview</h4>
          {Object.entries(report.narrative).map(([section, text]) => (
            <div key={section} className="rounded border border-border bg-surface p-3">
              <div className="text-xs font-semibold text-text-muted">
                {formatBoardReportSection(section)}
              </div>
              <p className="mt-1 text-sm leading-relaxed">{text}</p>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onRefresh}
          className="rounded-md border border-border bg-surface px-3 py-1.5 text-xs font-medium hover:bg-elevated"
        >
          Refresh status
        </button>
        {canDownload && (
          <button
            type="button"
            onClick={onDownload}
            className="rounded-md bg-brand-primary px-3 py-1.5 text-xs font-medium text-white"
          >
            Download PDF
          </button>
        )}
        {canApprove && report.status === "ready" && (
          <button
            type="button"
            onClick={onApprove}
            disabled={approving}
            className="rounded-md border border-positive/40 bg-positive/10 px-3 py-1.5 text-xs font-medium text-positive disabled:opacity-50"
          >
            {approving ? "Approving…" : "Approve report"}
          </button>
        )}
      </div>
    </div>
  );
}

export default function BoardReportsPage() {
  const periodDefaults = useMemo(() => defaultPeriod(), []);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [reports, setReports] = useState<BoardReportSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<BoardReportDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [title, setTitle] = useState("Q2 2026 Board Pack");
  const [template, setTemplate] = useState<BoardReportTemplate>("standard");
  const [periodStart, setPeriodStart] = useState(periodDefaults.start);
  const [periodEnd, setPeriodEnd] = useState(periodDefaults.end);
  const [sections, setSections] = useState<BoardReportSection[]>(
    BOARD_REPORT_TEMPLATES[0]!.sections,
  );
  const [generating, setGenerating] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [approving, setApproving] = useState(false);

  const refreshList = useCallback(async () => {
    const list = await listBoardReports();
    setReports(list);
  }, []);

  useEffect(() => {
    Promise.all([getMe(), listBoardReports()])
      .then(([me, list]) => {
        setUser(me);
        setReports(list);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    getBoardReport(selectedId)
      .then(setDetail)
      .catch((e: Error) => setError(e.message));
  }, [selectedId]);

  const onTemplateChange = (next: BoardReportTemplate) => {
    setTemplate(next);
    const tpl = BOARD_REPORT_TEMPLATES.find((t) => t.id === next);
    if (tpl) setSections(tpl.sections);
  };

  const toggleSection = (id: BoardReportSection) => {
    setSections((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id],
    );
  };

  const pollReport = useCallback(async (reportId: string) => {
    for (let attempt = 0; attempt < 60; attempt++) {
      const report = await getBoardReport(reportId);
      setDetail(report);
      setReports((prev) => {
        const idx = prev.findIndex((r) => r.id === reportId);
        const summary: BoardReportSummary = {
          id: report.id,
          title: report.title,
          period_start: report.period_start,
          period_end: report.period_end,
          sections: report.sections,
          status: report.status,
          template: report.template,
          created_at: report.created_at,
          generated_at: report.generated_at,
          export_url: report.export_url,
        };
        if (idx >= 0) {
          const next = [...prev];
          next[idx] = summary;
          return next;
        }
        return [summary, ...prev];
      });
      if (
        report.status === "ready" ||
        report.status === "approved" ||
        report.status === "published" ||
        report.status === "failed"
      ) {
        setProgress(100);
        return report;
      }
      setProgress(Math.min(95, 15 + attempt * 4));
      await new Promise((r) => setTimeout(r, 800));
    }
    throw new Error("Report generation timed out");
  }, []);

  const onGenerate = async () => {
    if (!title.trim()) {
      setError("Enter a title for the board pack");
      return;
    }
    if (sections.length === 0) {
      setError("Select at least one section");
      return;
    }
    if (periodStart > periodEnd) {
      setError("Period start must be before end");
      return;
    }

    setGenerating(true);
    setError(null);
    setProgress(0);

    try {
      const created = await createBoardReport({
        title: title.trim(),
        period_start: periodStart,
        period_end: periodEnd,
        sections,
        template,
      });
      setSelectedId(created.id);
      setProgress(10);
      await generateBoardReport(created.id);
      setProgress(20);
      await pollReport(created.id);
      await refreshList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  };

  const onApprove = async () => {
    if (!selectedId) return;
    setApproving(true);
    setError(null);
    try {
      await approveBoardReport(selectedId);
      const report = await getBoardReport(selectedId);
      setDetail(report);
      await refreshList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Approval failed");
    } finally {
      setApproving(false);
    }
  };

  const refreshDetail = async () => {
    if (!selectedId) return;
    try {
      const report = await getBoardReport(selectedId);
      setDetail(report);
      await refreshList();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Refresh failed");
    }
  };

  const canApprove = user?.permissions.includes("approve:board_report") ?? false;

  return (
    <div className="p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Board Reports</h1>
        <p className="text-sm text-text-muted">
          Generate narrated board packs with KPIs, forecasts, risk, and scenarios — export when
          ready.
        </p>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning">
          {error}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-6">
          <div className="rounded-lg border border-border bg-surface p-5">
            <h2 className="text-sm font-semibold">Generate board pack</h2>
            <p className="mt-1 text-xs text-text-muted">
              Choose a template, period, and sections — generation runs asynchronously.
            </p>

            <label className="mt-4 block text-sm">
              <span className="text-text-muted">Title</span>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 text-sm"
              />
            </label>

            <label className="mt-3 block text-sm">
              <span className="text-text-muted">Template</span>
              <select
                value={template}
                onChange={(e) => onTemplateChange(e.target.value as BoardReportTemplate)}
                className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 text-sm"
              >
                {BOARD_REPORT_TEMPLATES.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <label className="block text-sm">
                <span className="text-text-muted">Period start</span>
                <input
                  type="date"
                  value={periodStart}
                  onChange={(e) => setPeriodStart(e.target.value)}
                  className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 text-sm"
                />
              </label>
              <label className="block text-sm">
                <span className="text-text-muted">Period end</span>
                <input
                  type="date"
                  value={periodEnd}
                  onChange={(e) => setPeriodEnd(e.target.value)}
                  className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 text-sm"
                />
              </label>
            </div>

            <fieldset className="mt-4">
              <legend className="text-sm text-text-muted">Include sections</legend>
              <div className="mt-2 space-y-2">
                {BOARD_REPORT_SECTIONS.map((section) => (
                  <label
                    key={section.id}
                    className="flex cursor-pointer items-start gap-3 rounded-md border border-border bg-elevated px-3 py-2 hover:bg-surface"
                  >
                    <input
                      type="checkbox"
                      checked={sections.includes(section.id)}
                      onChange={() => toggleSection(section.id)}
                      className="mt-0.5"
                    />
                    <span>
                      <span className="block text-sm font-medium">{section.label}</span>
                      <span className="block text-xs text-text-muted">{section.description}</span>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>

            <button
              type="button"
              onClick={onGenerate}
              disabled={generating}
              className="mt-4 w-full rounded-md bg-brand-primary py-2.5 text-sm font-medium text-white disabled:opacity-50"
            >
              {generating ? `Generating… ${progress ?? 0}%` : "Generate board pack"}
            </button>

            {generating && progress !== null && (
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-elevated">
                <div
                  className="h-full bg-brand-primary transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            )}

            {canApprove && (
              <p className="mt-2 text-xs text-text-muted">
                You can approve reports once generation completes.
              </p>
            )}
          </div>
        </section>

        <section className="rounded-lg border border-border bg-surface p-5">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">Recent reports</h2>
            <span className="text-xs text-text-muted">
              {loading ? "Loading…" : `${reports.length} report${reports.length === 1 ? "" : "s"}`}
            </span>
          </div>
          <p className="mt-1 text-xs text-text-muted">
            Select a report for metadata, narrative preview, and download.
          </p>

          {reports.length === 0 && !loading ? (
            <p className="mt-4 rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-text-muted">
              No board reports yet — generate your first pack above.
            </p>
          ) : (
            <div className="mt-4 overflow-hidden rounded-md border border-border">
              {reports.map((report) => (
                <ReportRow
                  key={report.id}
                  report={report}
                  selected={selectedId === report.id}
                  onSelect={setSelectedId}
                />
              ))}
            </div>
          )}

          {detail && selectedId === detail.id && (
            <ReportDetailPanel
              report={detail}
              user={user}
              onRefresh={refreshDetail}
              onApprove={onApprove}
              approving={approving}
            />
          )}
        </section>
      </div>
    </div>
  );
}
