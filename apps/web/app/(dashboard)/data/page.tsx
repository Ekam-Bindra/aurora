"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  createDataSource,
  dataSourceStatusTone,
  formatDataSourceKind,
  formatMetricLabel,
  getIngestionJob,
  ingestionJobStatusTone,
  listDataSources,
  listIngestionJobs,
  syncDataSource,
  uploadIngestionFile,
  type DataSource,
  type DataSourceKind,
  type IngestionJobDetail,
  type IngestionJobSummary,
  type IngestionTarget,
} from "@/lib/api";

const INGESTION_TARGETS: IngestionTarget[] = [
  "invoices",
  "expenses",
  "customers",
  "vendors",
];

const SOURCE_KINDS: DataSourceKind[] = ["file", "accounting", "crm", "hris", "api"];

const STATUS_TEXT: Record<string, string> = {
  positive: "text-positive",
  warning: "text-warning",
  negative: "text-negative",
  muted: "text-text-muted",
};

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
      {label}
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

function SourceCard({
  source,
  onSync,
  syncing,
}: {
  source: DataSource;
  onSync: (id: string) => void;
  syncing: boolean;
}) {
  const tone = dataSourceStatusTone(source.status);
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold">{source.name}</h3>
          <p className="mt-0.5 text-xs text-text-muted">{formatDataSourceKind(source.kind)}</p>
        </div>
        <StatusBadge label={source.status} tone={tone} />
      </div>
      <dl className="mt-3 space-y-1 text-xs">
        <div className="flex justify-between gap-4">
          <dt className="text-text-muted">Last sync</dt>
          <dd className="tabular-nums">{formatTimestamp(source.last_synced_at)}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-text-muted">Health</dt>
          <dd className={STATUS_TEXT[tone]}>
            {source.status === "connected"
              ? "Healthy"
              : source.status === "syncing"
                ? "Sync in progress"
                : source.status === "error"
                  ? "Needs attention"
                  : "Disabled"}
          </dd>
        </div>
      </dl>
      {source.kind !== "file" && source.status !== "disabled" && (
        <button
          type="button"
          onClick={() => onSync(source.id)}
          disabled={syncing || source.status === "syncing"}
          className="mt-3 w-full rounded-md border border-border bg-elevated py-1.5 text-xs font-medium hover:bg-surface disabled:opacity-50"
        >
          {syncing ? "Syncing…" : "Sync now"}
        </button>
      )}
    </div>
  );
}

function JobRow({
  job,
  selected,
  onSelect,
}: {
  job: IngestionJobSummary;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const tone = ingestionJobStatusTone(job.status);
  return (
    <button
      type="button"
      onClick={() => onSelect(job.job_id)}
      className={`w-full border-t border-border/60 px-3 py-2.5 text-left text-sm transition first:border-t-0 ${
        selected ? "bg-elevated" : "hover:bg-elevated/60"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium capitalize">{formatMetricLabel(job.target)}</span>
        <StatusBadge label={job.status} tone={tone} />
      </div>
      <div className="mt-1 flex flex-wrap gap-x-3 text-xs text-text-muted">
        <span>{formatTimestamp(job.started_at)}</span>
        {job.rows_total !== undefined && (
          <span className="tabular-nums">{job.rows_total.toLocaleString()} rows</span>
        )}
        {(job.rows_rejected ?? 0) > 0 && (
          <span className="text-negative tabular-nums">
            {job.rows_rejected} rejected
          </span>
        )}
      </div>
    </button>
  );
}

function JobDetailPanel({ job }: { job: IngestionJobDetail }) {
  const tone = ingestionJobStatusTone(job.status);
  const rejected = job.errors?.filter((e) => e.action === "rejected") ?? job.errors ?? [];

  return (
    <div className="mt-4 rounded-md border border-border bg-elevated p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Job detail</h3>
        <StatusBadge label={job.status} tone={tone} />
      </div>

      <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        <div className="flex justify-between gap-4 sm:block">
          <dt className="text-text-muted">Target</dt>
          <dd className="capitalize">{formatMetricLabel(job.target)}</dd>
        </div>
        <div className="flex justify-between gap-4 sm:block">
          <dt className="text-text-muted">Started</dt>
          <dd>{formatTimestamp(job.started_at)}</dd>
        </div>
        <div className="flex justify-between gap-4 sm:block">
          <dt className="text-text-muted">Finished</dt>
          <dd>{formatTimestamp(job.finished_at)}</dd>
        </div>
        {job.lineage_ref && (
          <div className="sm:col-span-2">
            <dt className="text-xs font-semibold uppercase tracking-wide text-text-muted">
              Lineage
            </dt>
            <dd className="mt-1 break-all rounded border border-border bg-surface px-2 py-1.5 font-mono text-xs">
              {job.lineage_ref}
            </dd>
          </div>
        )}
      </dl>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          { label: "Total", value: job.rows_total },
          { label: "Inserted", value: job.rows_inserted },
          { label: "Updated", value: job.rows_updated },
          { label: "Rejected", value: job.rows_rejected },
        ].map(({ label, value }) => (
          <div key={label} className="rounded border border-border bg-surface px-3 py-2">
            <div className="text-xs text-text-muted">{label}</div>
            <div
              className={`mt-0.5 text-lg font-semibold tabular-nums ${
                label === "Rejected" && (value ?? 0) > 0 ? "text-negative" : ""
              }`}
            >
              {value !== undefined ? value.toLocaleString() : "—"}
            </div>
          </div>
        ))}
      </div>

      {rejected.length > 0 && (
        <div className="mt-4">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            Rejected rows
          </h4>
          <div className="mt-2 max-h-48 overflow-auto rounded border border-border">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface">
                <tr className="text-left text-xs text-text-muted">
                  <th className="px-3 py-2">Row</th>
                  <th className="px-3 py-2">Issue</th>
                  <th className="px-3 py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {rejected.map((err, i) => (
                  <tr key={`${err.row}-${i}`} className="border-t border-border/60">
                    <td className="px-3 py-2 tabular-nums">{err.row}</td>
                    <td className="px-3 py-2 text-text-muted">{err.issue}</td>
                    <td className="px-3 py-2 capitalize">{err.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default function DataSourcesPage() {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [jobs, setJobs] = useState<IngestionJobSummary[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [jobDetail, setJobDetail] = useState<IngestionJobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const [uploadTarget, setUploadTarget] = useState<IngestionTarget>("invoices");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [mappingJson, setMappingJson] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [newSourceName, setNewSourceName] = useState("");
  const [newSourceKind, setNewSourceKind] = useState<DataSourceKind>("file");
  const [registering, setRegistering] = useState(false);
  const [syncingId, setSyncingId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const [src, jbs] = await Promise.all([listDataSources(), listIngestionJobs()]);
    setSources(src);
    setJobs(jbs);
  }, []);

  useEffect(() => {
    Promise.resolve()
      .then(refresh)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [refresh]);

  useEffect(() => {
    // Selection is never cleared once made, and the detail panel renders only
    // when the loaded detail matches the selection, so no reset is needed here.
    if (!selectedJobId) return;
    getIngestionJob(selectedJobId)
      .then(setJobDetail)
      .catch((e: Error) => setError(e.message));
  }, [selectedJobId]);

  const pollJob = useCallback(async (jobId: string) => {
    for (let attempt = 0; attempt < 60; attempt++) {
      const job = await getIngestionJob(jobId);
      setJobDetail(job);
      setJobs((prev) => {
        const idx = prev.findIndex((j) => j.job_id === jobId);
        const summary: IngestionJobSummary = {
          job_id: job.job_id,
          status: job.status,
          target: job.target,
          source_id: job.source_id,
          rows_total: job.rows_total,
          rows_inserted: job.rows_inserted,
          rows_updated: job.rows_updated,
          rows_rejected: job.rows_rejected,
          started_at: job.started_at,
          finished_at: job.finished_at,
        };
        if (idx >= 0) {
          const next = [...prev];
          next[idx] = summary;
          return next;
        }
        return [summary, ...prev];
      });
      if (job.status === "completed" || job.status === "failed" || job.status === "cancelled") {
        setUploadProgress(100);
        return job;
      }
      setUploadProgress(Math.min(95, 15 + attempt * 4));
      await new Promise((r) => setTimeout(r, 800));
    }
    throw new Error("Ingestion job timed out");
  }, []);

  const onUpload = async () => {
    if (!uploadFile) {
      setError("Select a CSV or XLSX file to upload");
      return;
    }

    let mapping: Record<string, string> | undefined;
    if (mappingJson.trim()) {
      try {
        mapping = JSON.parse(mappingJson) as Record<string, string>;
      } catch {
        setError("Schema mapping must be valid JSON");
        return;
      }
    }

    setUploading(true);
    setError(null);
    setUploadProgress(0);

    try {
      const launched = await uploadIngestionFile({
        file: uploadFile,
        target: uploadTarget,
        mapping,
      });
      setSelectedJobId(launched.job_id);
      setUploadProgress(10);
      await pollJob(launched.job_id);
      await refresh();
      setUploadFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const onRegisterSource = async () => {
    if (!newSourceName.trim()) {
      setError("Enter a name for the data source");
      return;
    }
    setRegistering(true);
    setError(null);
    try {
      await createDataSource({ kind: newSourceKind, name: newSourceName.trim() });
      setNewSourceName("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Registration failed");
    } finally {
      setRegistering(false);
    }
  };

  const onSync = async (sourceId: string) => {
    setSyncingId(sourceId);
    setError(null);
    try {
      const launched = await syncDataSource(sourceId);
      setSelectedJobId(launched.job_id);
      await pollJob(launched.job_id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncingId(null);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) setUploadFile(file);
  };

  return (
    <div className="p-8">
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Data Sources</h1>
        <p className="text-sm text-text-muted">
          Register connectors, upload files, monitor ingestion health, and drill into rejected rows
          and lineage.
        </p>
      </header>

      {error && (
        <div className="mb-4 rounded-lg border border-warning/40 bg-warning/10 px-4 py-3 text-sm text-warning">
          {error}
        </div>
      )}

      <section className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Registered sources</h2>
          <span className="text-xs text-text-muted">
            {loading ? "Loading…" : `${sources.length} source${sources.length === 1 ? "" : "s"}`}
          </span>
        </div>
        {sources.length === 0 && !loading ? (
          <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-text-muted">
            No data sources yet — register one below or upload a file to get started.
          </p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {sources.map((src) => (
              <SourceCard
                key={src.id}
                source={src}
                onSync={onSync}
                syncing={syncingId === src.id}
              />
            ))}
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-6">
          <div className="rounded-lg border border-border bg-surface p-5">
            <h2 className="text-sm font-semibold">Register source</h2>
            <p className="mt-1 text-xs text-text-muted">
              Add a file drop or connector before scheduling syncs.
            </p>
            <label className="mt-4 block text-sm">
              <span className="text-text-muted">Name</span>
              <input
                type="text"
                value={newSourceName}
                onChange={(e) => setNewSourceName(e.target.value)}
                placeholder="e.g. QuickBooks Production"
                className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 text-sm"
              />
            </label>
            <label className="mt-3 block text-sm">
              <span className="text-text-muted">Kind</span>
              <select
                value={newSourceKind}
                onChange={(e) => setNewSourceKind(e.target.value as DataSourceKind)}
                className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 text-sm"
              >
                {SOURCE_KINDS.map((k) => (
                  <option key={k} value={k}>
                    {formatDataSourceKind(k)}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              onClick={onRegisterSource}
              disabled={registering}
              className="mt-4 w-full rounded-md border border-border bg-elevated py-2 text-sm font-medium hover:bg-surface disabled:opacity-50"
            >
              {registering ? "Registering…" : "Register source"}
            </button>
          </div>

          <div className="rounded-lg border border-border bg-surface p-5">
            <h2 className="text-sm font-semibold">File upload</h2>
            <p className="mt-1 text-xs text-text-muted">
              CSV or XLSX for core entities — optional column mapping as JSON.
            </p>

            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={onDrop}
              className="mt-4 rounded-md border-2 border-dashed border-border bg-elevated px-4 py-8 text-center"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".csv,.xlsx,.xls"
                className="hidden"
                id="ingestion-file"
                onChange={(e) => setUploadFile(e.target.files?.[0] ?? null)}
              />
              <label htmlFor="ingestion-file" className="cursor-pointer text-sm">
                {uploadFile ? (
                  <span className="font-medium">{uploadFile.name}</span>
                ) : (
                  <>
                    <span className="text-brand-accent hover:underline">Choose a file</span>
                    <span className="text-text-muted"> or drag and drop</span>
                  </>
                )}
              </label>
            </div>

            <label className="mt-4 block text-sm">
              <span className="text-text-muted">Target entity</span>
              <select
                value={uploadTarget}
                onChange={(e) => setUploadTarget(e.target.value as IngestionTarget)}
                className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 text-sm capitalize"
              >
                {INGESTION_TARGETS.map((t) => (
                  <option key={t} value={t}>
                    {formatMetricLabel(t)}
                  </option>
                ))}
              </select>
            </label>

            <label className="mt-3 block text-sm">
              <span className="text-text-muted">Schema mapping (optional JSON)</span>
              <textarea
                value={mappingJson}
                onChange={(e) => setMappingJson(e.target.value)}
                placeholder='{"invoice_no": "Invoice Number", "amount": "Total"}'
                rows={3}
                className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 font-mono text-xs"
              />
            </label>

            <button
              type="button"
              onClick={onUpload}
              disabled={uploading || !uploadFile}
              className="mt-4 w-full rounded-md bg-brand-primary py-2.5 text-sm font-medium text-white disabled:opacity-50"
            >
              {uploading ? `Uploading… ${uploadProgress ?? 0}%` : "Upload & ingest"}
            </button>

            {uploading && uploadProgress !== null && (
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-elevated">
                <div
                  className="h-full bg-brand-primary transition-all"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
            )}
          </div>
        </section>

        <section className="rounded-lg border border-border bg-surface p-5">
          <h2 className="text-sm font-semibold">Ingestion jobs</h2>
          <p className="mt-1 text-xs text-text-muted">
            Recent uploads and syncs — select a job for counts, lineage, and rejected rows.
          </p>

          {jobs.length === 0 && !loading ? (
            <p className="mt-4 text-sm text-text-muted">No ingestion jobs yet.</p>
          ) : (
            <div className="mt-4 overflow-hidden rounded-md border border-border">
              {jobs.map((job) => (
                <JobRow
                  key={job.job_id}
                  job={job}
                  selected={selectedJobId === job.job_id}
                  onSelect={setSelectedJobId}
                />
              ))}
            </div>
          )}

          {jobDetail && selectedJobId === jobDetail.job_id && <JobDetailPanel job={jobDetail} />}
        </section>
      </div>
    </div>
  );
}
