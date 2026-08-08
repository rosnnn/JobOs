"use client";

import { useCallback, useEffect, useState } from "react";
import { PageLoader, Spinner, TableSkeleton } from "@/components/Loading";
import { api, type EmailMessage, type RejectionAnalytics } from "@/lib/api";

const OUTCOME_LABELS: Record<string, string> = {
  rejected: "Rejected",
  interview_request: "Interview",
  offer: "Offer",
  accepted: "Accepted",
  application_received: "App received",
  employer_update: "Employer update",
  job_recommendation: "Job alert",
  promotional: "Promo / ads",
  sponsorship_ad: "Sponsorship ad",
  security: "Security",
  hr_outreach: "HR outreach",
  newsletter: "Newsletter",
  job_related: "Job related",
  general_notification: "Notification",
};

const FILTER_OPTIONS = [
  { value: "", label: "All" },
  { value: "rejected", label: "Rejected" },
  { value: "interview_request", label: "Interview" },
  { value: "offer", label: "Offer" },
  { value: "application_received", label: "App received" },
  { value: "employer_update", label: "Employer" },
  { value: "job_recommendation", label: "Job alerts" },
  { value: "promotional", label: "Promo" },
  { value: "security", label: "Security" },
  { value: "hr_outreach", label: "HR" },
  { value: "general_notification", label: "Other mails" },
];

function outcomeBadgeClass(outcome: string | null): string {
  const o = (outcome || "general_notification").replace(/_/g, "-");
  if (OUTCOME_LABELS[outcome || ""]) return `badge-outcome-${o}`;
  return "badge-outcome-general-notification";
}

export default function InboxPage() {
  const [messages, setMessages] = useState<EmailMessage[]>([]);
  const [analytics, setAnalytics] = useState<RejectionAnalytics | null>(null);
  const [stats, setStats] = useState<Record<string, number>>({});
  const [mailStatus, setMailStatus] = useState<{
    configured: boolean;
    connected: boolean;
    address: string | null;
    error: string | null;
  } | null>(null);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [syncLoading, setSyncLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [syncMsg, setSyncMsg] = useState<string | null>(null);
  const [initialDone, setInitialDone] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [creds, msgs, a, st] = await Promise.all([
        api.emailStatus().catch(() => ({ configured: false, connected: false, address: null, error: null })),
        api.emailMessages(filter || undefined),
        api.rejectionAnalytics().catch(() => null),
        api.emailStats().catch(() => ({ total: 0, by_outcome: {} })),
      ]);
      setMailStatus({
        configured: creds.configured,
        connected: creds.connected,
        address: creds.address || null,
        error: creds.error || (creds.configured ? "Gmail login failed" : "Save Gmail credentials in Profile first"),
      });
      setMessages(msgs);
      setAnalytics(a);
      setStats(st.by_outcome);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load inbox");
    } finally {
      setLoading(false);
      setInitialDone(true);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  async function sync() {
    setSyncLoading(true);
    setSyncMsg(null);
    setError(null);
    try {
      await api.reclassifyEmails();
      const r = await api.syncEmail();
      if (r.error) {
        setError(r.error);
      } else {
        const parts = [];
        if (r.synced) parts.push(`${r.synced} new`);
        if (r.reclassified) parts.push(`${r.reclassified} reclassified`);
        setSyncMsg(parts.length ? `Synced: ${parts.join(", ")}` : `Sync finished: ${r.status}`);
      }
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncLoading(false);
    }
  }

  if (loading && !initialDone) {
    return (
      <>
        <h1 className="page-title">Inbox</h1>
        <p className="page-sub">Loading inbox…</p>
        <PageLoader label="Connecting to Gmail and fetching emails…" />
      </>
    );
  }

  const topCategories = Object.entries(stats)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);

  return (
    <>
      <h1 className="page-title">Inbox</h1>
      <p className="page-sub">
        Smart labels: job alerts, rejections, promos, security, HR — not just &quot;unknown&quot;
      </p>

      {mailStatus && !mailStatus.connected && (
        <div className="alert alert-error">
          <strong>Gmail not connected.</strong> {mailStatus.error || "Check GMAIL_APP_PASSWORD in .env"}
        </div>
      )}

      {mailStatus?.connected && (
        <div className="alert alert-success">Connected to {mailStatus.address}</div>
      )}

      {topCategories.length > 0 && (
        <div className="grid" style={{ marginBottom: "1.5rem" }}>
          {topCategories.map(([k, v]) => (
            <div key={k} className="card" style={{ padding: "0.75rem 1rem" }}>
              <h3>{OUTCOME_LABELS[k] || k}</h3>
              <div className="value" style={{ fontSize: "1.25rem" }}>
                {v}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="actions" style={{ flexWrap: "wrap" }}>
        <button
          className="btn btn-primary"
          onClick={sync}
          disabled={syncLoading || loading || !mailStatus?.connected}
        >
          {syncLoading ? "Syncing…" : "Sync & reclassify"}
        </button>
        {FILTER_OPTIONS.map((f) => (
          <button
            key={f.value || "all"}
            className={`btn ${filter === f.value ? "btn-primary" : "btn-secondary"}`}
            onClick={() => setFilter(f.value)}
            disabled={loading}
          >
            {f.label}
          </button>
        ))}
      </div>

      {syncMsg && <div className="alert alert-success">{syncMsg}</div>}
      {error && <div className="alert alert-error">{error}</div>}

      {loading ? (
        <>
          <div className="status-line" style={{ marginBottom: "1rem" }}>
            <Spinner label="Loading emails…" />
          </div>
          <TableSkeleton rows={8} cols={5} />
        </>
      ) : (
        <>
          {analytics && analytics.suggestions.length > 0 && (
            <div className="card" style={{ marginBottom: "1.5rem" }}>
              <h3>AI rejection insights ({analytics.total_rejections} rejections)</h3>
              <ul style={{ paddingLeft: "1.25rem", fontSize: "0.875rem", marginTop: "0.5rem" }}>
                {analytics.suggestions.map((s, i) => (
                  <li key={i} style={{ marginBottom: "0.35rem", color: "var(--muted)" }}>
                    {s}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>From</th>
                  <th>Subject</th>
                  <th>Type</th>
                  <th>Walk-in</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {messages.map((m) => (
                  <tr key={m.id}>
                    <td style={{ fontSize: "0.8rem" }} title={m.from_address}>
                      {m.from_address.slice(0, 42)}
                    </td>
                    <td title={m.subject}>{m.subject.slice(0, 55)}{m.subject.length > 55 ? "…" : ""}</td>
                    <td>
                      <span className={`badge ${outcomeBadgeClass(m.classified_outcome)}`}>
                        {OUTCOME_LABELS[m.classified_outcome || ""] ||
                          (m.classified_outcome || "Notification").replace(/_/g, " ")}
                      </span>
                    </td>
                    <td>{m.is_walk_in ? "Yes" : "—"}</td>
                    <td>{m.received_at ? new Date(m.received_at).toLocaleDateString() : "—"}</td>
                  </tr>
                ))}
                {messages.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ color: "var(--muted)", textAlign: "center" }}>
                      {mailStatus?.connected
                        ? "No emails in this filter — click Sync & reclassify"
                        : "Fix Gmail connection above first"}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}
