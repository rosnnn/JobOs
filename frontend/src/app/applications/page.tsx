"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Spinner, TableSkeleton } from "@/components/Loading";
import { api, type Application } from "@/lib/api";

function decodeHtmlEntities(text: string): string {
  if (!text) return text;
  return text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/Ã©/g, "é")
    .replace(/Ã´/g, "ô")
    .replace(/Ã /g, "à");
}

const OUTCOME_BADGE: Record<string, string> = {
  rejected: "badge-rejected",
  interview_request: "badge-interview",
  offer: "badge-offer",
  accepted: "badge-approved",
};

export default function ApplicationsPage() {
  const [apps, setApps] = useState<Application[]>([]);
  const [filter, setFilter] = useState<string>("");
  const [outcomeFilter, setOutcomeFilter] = useState<string>("");
  const [dryRun, setDryRun] = useState(true);
  const [bulkMsg, setBulkMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [bulkLoading, setBulkLoading] = useState(false);
  const [initialDone, setInitialDone] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.applications({
        approval_status: filter || undefined,
        outcome: outcomeFilter || undefined,
      });
      setApps(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
      setInitialDone(true);
    }
  }, [filter, outcomeFilter]);

  useEffect(() => {
    api.cleanupApplications().catch(() => null).finally(() => load());
  }, [load]);

  return (
    <>
      <h1 className="page-title">Applications</h1>
      <p className="page-sub">
        Cancelled and duplicate rows are hidden. Bulk dry-run applies up to 5 roles (~3 min).
      </p>

      <div className="actions">
        <button
          className="btn btn-success"
          disabled={bulkLoading || loading}
          onClick={async () => {
            setError(null);
            setBulkMsg(null);
            setBulkLoading(true);
            setBulkMsg("Approving and dry-running up to 5 applications (about 2–4 minutes)…");
            try {
              const r = await api.approveAllAndApply(dryRun);
              const cancelled = r.cancelled_irrelevant ?? 0;
              const ok = r.apply_ok ?? 0;
              const skipped = r.apply_skipped ?? 0;
              const failed = r.apply_failed ?? 0;
              const withAudit = (r.apply_results ?? []).filter(
                (x: { form_audit?: { filled?: number } }) => x.form_audit && (x.form_audit.filled ?? 0) > 0,
              ).length;
              const captcha = (r.apply_results ?? []).filter(
                (x: { status?: string }) => x.status === "awaiting_captcha",
              ).length;
              setBulkMsg(
                `Dupes removed ${r.duplicates_cancelled ?? 0} · cancelled ${cancelled} non-software · approved ${r.approved_count} · ` +
                  `${r.dry_run ? "dry-run" : "REAL"} apply: ${ok} ok, ${skipped} listing-only, ${failed} failed` +
                  (withAudit ? ` · ${withAudit} with form reports` : "") +
                  (captcha ? ` · ${captcha} need CAPTCHA` : "") +
                  ` · ${r.status}`,
              );
              await load();
            } catch (e) {
              const err = e instanceof Error ? e.message : "Bulk apply failed";
              setError(
                err.includes("abort")
                  ? "Timed out — try again or dry-run one job from its Review page."
                  : err,
              );
            } finally {
              setBulkLoading(false);
            }
          }}
        >
          {bulkLoading ? "Applying…" : "Approve all & Apply"}
        </button>
        <label className="filter-check" style={{ alignSelf: "center" }}>
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          Dry-run
        </label>
        <button className={`btn ${filter === "" ? "btn-primary" : "btn-secondary"}`} onClick={() => setFilter("")} disabled={loading}>
          All
        </button>
        <button
          className={`btn ${filter === "pending" ? "btn-primary" : "btn-secondary"}`}
          onClick={() => setFilter("pending")}
          disabled={loading}
        >
          Pending
        </button>
        <button
          className={`btn ${filter === "approved" ? "btn-primary" : "btn-secondary"}`}
          onClick={() => setFilter("approved")}
          disabled={loading}
        >
          Approved
        </button>
        <span style={{ color: "var(--border)", margin: "0 0.25rem" }}>|</span>
        <button
          className={`btn ${outcomeFilter === "rejected" ? "btn-primary" : "btn-secondary"}`}
          onClick={() => setOutcomeFilter(outcomeFilter === "rejected" ? "" : "rejected")}
          disabled={loading}
        >
          Rejected
        </button>
        <button
          className={`btn ${outcomeFilter === "interview_request" ? "btn-primary" : "btn-secondary"}`}
          onClick={() =>
            setOutcomeFilter(outcomeFilter === "interview_request" ? "" : "interview_request")
          }
          disabled={loading}
        >
          Interviews
        </button>
        <button
          className={`btn ${outcomeFilter === "offer" ? "btn-primary" : "btn-secondary"}`}
          onClick={() => setOutcomeFilter(outcomeFilter === "offer" ? "" : "offer")}
          disabled={loading}
        >
          Offers
        </button>
        <button className="btn btn-secondary" onClick={load} disabled={loading}>
          Refresh
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {bulkMsg && <div className="alert alert-success">{bulkMsg}</div>}

      {loading && !initialDone ? (
        <>
          <div className="status-line" style={{ color: "var(--muted)", fontSize: "0.875rem", marginBottom: "1rem" }}>
            <Spinner label="Loading applications…" />
          </div>
          <TableSkeleton rows={8} cols={6} />
        </>
      ) : loading ? (
        <>
          <div className="status-line" style={{ color: "var(--muted)", fontSize: "0.875rem", marginBottom: "1rem" }}>
            <Spinner label="Updating…" />
          </div>
          <TableSkeleton rows={6} cols={6} />
        </>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Job</th>
                <th>Company</th>
                <th>Status</th>
                <th>Outcome</th>
                <th>Rejection reason</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {apps.map((a) => (
                <tr key={a.id}>
                  <td>{decodeHtmlEntities(a.job_title || "—")}</td>
                  <td>{decodeHtmlEntities(a.company_name || "—")}</td>
                  <td>
                    <span className="badge badge-draft">{a.status}</span>
                  </td>
                  <td>
                    {a.outcome ? (
                      <span className={`badge ${OUTCOME_BADGE[a.outcome] || "badge-draft"}`}>
                        {a.outcome.replace("_", " ")}
                      </span>
                    ) : a.status === "cancelled" ? (
                      <span className="badge badge-draft">cancelled</span>
                    ) : (
                      <span className="badge badge-pending">awaiting reply</span>
                    )}
                  </td>
                  <td style={{ maxWidth: 280, fontSize: "0.8rem", color: "var(--muted)" }}>
                    {a.rejection_reason
                      ? a.rejection_reason.slice(0, 120) + (a.rejection_reason.length > 120 ? "…" : "")
                      : a.metadata?.apply_note
                        ? String(a.metadata.apply_note).slice(0, 120)
                        : a.metadata?.last_error
                          ? String(a.metadata.last_error).slice(0, 120)
                          : a.metadata?.walk_in
                            ? "Walk-in interview flagged"
                            : "—"}
                  </td>
                  <td>
                    <Link href={`/applications/${a.id}`}>Review →</Link>
                  </td>
                </tr>
              ))}
              {apps.length === 0 && (
                <tr>
                  <td colSpan={6} style={{ color: "var(--muted)", textAlign: "center" }}>
                    No applications yet — run Auto Apply from Dashboard
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
