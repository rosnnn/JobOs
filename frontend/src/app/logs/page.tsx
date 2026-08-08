"use client";

import { useEffect, useState } from "react";
import { PageLoader } from "@/components/Loading";
import { api, type EventRow } from "@/lib/api";

function toSummary(row: EventRow): string {
  const p = row.payload || {};
  if (row.event_type === "jobs.live_sync_completed") {
    const discovered = Number(p.discovered_count || 0);
    const matched = Number(p.jobs_for_profile || 0);
    const dupes = Number(p.purged_duplicates || 0);
    const bySource = p.by_source && typeof p.by_source === "object" ? (p.by_source as Record<string, number>) : {};
    const bySourceStatus =
      p.by_source_status && typeof p.by_source_status === "object"
        ? (p.by_source_status as Record<string, { last_status?: string }>)
        : {};
    const top = Object.entries(bySource)
      .sort((a, b) => Number(b[1]) - Number(a[1]))
      .slice(0, 6)
      .map(([src, count]) => `${src}:${count}`)
      .join(" | ");
    const boardState = `linkedin:${bySourceStatus.linkedin?.last_status || "unknown"} | wellfound:${bySourceStatus.wellfound?.last_status || "unknown"}`;
    return `Live sync completed · discovered ${discovered} · matched ${matched} · duplicate removals ${dupes}${top ? ` · by source ${top}` : ""} · ${boardState}`;
  }
  if (row.event_type === "jobs.invalid_purged") {
    const rejected = Number(p.jobs_rejected || 0);
    const cancelled = Number(p.applications_cancelled || 0);
    return `Invalid cleanup · jobs rejected ${rejected} · applications cancelled ${cancelled}`;
  }
  if (row.event_type === "email.sync_completed" || row.event_type === "email_monitor.completed") {
    const synced = Number(p.synced || 0);
    const reclassified = Number(p.reclassified || 0);
    return `Email sync · new ${synced} · reclassified ${reclassified}`;
  }
  if (row.event_type === "workflow.completed" || row.event_type === "workflow.started") {
    const status = String(p.status || row.severity || "info");
    return `Workflow ${row.event_type.replace("workflow.", "")} · ${status}`;
  }
  const msg = typeof p.message === "string" ? p.message : "";
  return msg || JSON.stringify(p || {});
}

export default function LogsPage() {
  const [rows, setRows] = useState<EventRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const importantTypes = new Set([
    "jobs.live_sync_completed",
    "jobs.invalid_purged",
    "profile.credentials_updated",
    "profile.resume_uploaded",
    "profile.resume_ingested",
    "email.sync_completed",
    "email_monitor.completed",
    "workflow.completed",
    "workflow.step_failed",
  ]);

  useEffect(() => {
    let mounted = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const out = await api.events(200);
        if (mounted) setRows(out.filter((row) => importantTypes.has(row.event_type)));
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : "Failed to load logs");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <>
        <h1 className="page-title">Logs</h1>
        <p className="page-sub">Loading agent and system events…</p>
        <PageLoader label="Fetching logs…" />
      </>
    );
  }

  return (
    <>
      <h1 className="page-title">Logs</h1>
      <p className="page-sub">Recent job, email, profile, and workflow activity</p>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="alert alert-info" style={{ marginBottom: "1rem" }}>
        This page shows syncs, deletions, profile changes, and mail activity. Use it as the audit trail.
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Severity</th>
              <th>Source</th>
              <th>Event</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td>{new Date(row.created_at).toLocaleString()}</td>
                <td>{row.severity}</td>
                <td>{row.source}</td>
                <td>{row.event_type}</td>
                <td style={{ maxWidth: 500, whiteSpace: "pre-wrap", fontSize: "0.78rem" }}>
                  {toSummary(row)}
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={5} style={{ textAlign: "center", color: "var(--muted)" }}>
                  No logs yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
