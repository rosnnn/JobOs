"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { PageLoader } from "@/components/Loading";
import { FormFillReport, type FormAudit } from "@/components/FormFillReport";
import { api, type Application } from "@/lib/api";

export default function ApplicationDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [app, setApp] = useState<Application | null>(null);
  const [resume, setResume] = useState<string | null>(null);
  const [cover, setCover] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [lastAudit, setLastAudit] = useState<FormAudit | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    Promise.all([
      api.application(id),
      api.resume(id).then((r) => r.content_text).catch(() => null),
      api.coverLetter(id).then((c) => c.content_text).catch(() => null),
    ])
      .then(([a, r, c]) => {
        setApp(a);
        setResume(r);
        setCover(c);
        if (a.metadata?.form_audit) {
          setLastAudit(a.metadata.form_audit as FormAudit);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [id]);

  async function approve() {
    setActionLoading(true);
    setMsg(null);
    try {
      const updated = await api.approve(id);
      setApp(updated);
      setMsg("Approved ✓");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setActionLoading(false);
    }
  }

  async function submit(dryRun: boolean) {
    setActionLoading(true);
    setMsg(null);
    try {
      const result = await api.submit(id, dryRun);
      const userMsg =
        (result.user_message as string) ||
        (result.error as string) ||
        String(result.status || "unknown");
      const ok = Boolean(result.success);
      setMsg(
        dryRun
          ? ok
            ? userMsg
            : `Dry-run failed: ${userMsg}`
          : ok
            ? userMsg
            : `Submit failed: ${userMsg}`,
      );
      if (result.form_audit) {
        setLastAudit(result.form_audit as FormAudit);
      }
      const updated = await api.application(id);
      setApp(updated);
      if (updated.metadata?.form_audit) {
        setLastAudit(updated.metadata.form_audit as FormAudit);
      }
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Submit failed");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return (
      <>
        <Link href="/applications" style={{ fontSize: "0.875rem" }}>
          ← Back to applications
        </Link>
        <PageLoader label="Loading application details…" />
      </>
    );
  }

  if (!app) {
    return (
      <>
        <Link href="/applications" style={{ fontSize: "0.875rem" }}>
          ← Back to applications
        </Link>
        <div className="alert alert-error" style={{ marginTop: "1rem" }}>
          Application not found
        </div>
      </>
    );
  }

  return (
    <>
      <Link href="/applications" style={{ fontSize: "0.875rem" }}>
        ← Back to applications
      </Link>
      <h1 className="page-title" style={{ marginTop: "1rem" }}>
        {app.job_title}
      </h1>
      <p className="page-sub">
        {app.company_name} ·{" "}
        {app.job_url && (
          <a href={app.job_url} target="_blank" rel="noreferrer">
            View job posting
          </a>
        )}
      </p>

      {app.outcome === "rejected" && app.rejection_reason && (
        <div className="alert alert-error" style={{ marginTop: "1rem" }}>
          <strong>Why rejected:</strong> {app.rejection_reason}
        </div>
      )}
      {app.metadata?.rejection_analysis && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h3>AI fix suggestions</h3>
          <ul style={{ paddingLeft: "1.25rem", fontSize: "0.875rem", marginTop: "0.5rem" }}>
            {(
              (app.metadata.rejection_analysis as { suggestions?: string[] }).suggestions || []
            ).map((s, i) => (
              <li key={i} style={{ color: "var(--muted)", marginBottom: "0.35rem" }}>
                {s}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="actions">
        {app.approval_status !== "approved" && (
          <button className="btn btn-success" onClick={approve} disabled={actionLoading}>
            {actionLoading ? "Working…" : "Approve"}
          </button>
        )}
        <button className="btn btn-warning" onClick={() => submit(true)} disabled={actionLoading}>
          {actionLoading ? "Applying…" : "Dry-run apply (safe)"}
        </button>
        {app.approval_status === "approved" && (
          <button className="btn btn-primary" onClick={() => submit(false)} disabled={actionLoading}>
            Real submit
          </button>
        )}
      </div>

      {msg && (
        <div
          className={`alert ${
            msg.toLowerCase().includes("failed") ||
            msg.includes("not_applyable") ||
            msg.includes("no application form")
              ? "alert-error"
              : msg.includes("Dry-run OK") || msg.includes("submitted")
                ? "alert-success"
                : "alert-success"
          }`}
        >
          {msg}
        </div>
      )}

      {app.status === "not_applyable" && (app.metadata?.apply_note || app.metadata?.last_error) && (
        <div className="alert alert-error" style={{ marginTop: "0.75rem" }}>
          {String(app.metadata.apply_note || app.metadata.last_error)}
        </div>
      )}

      {(lastAudit || app.metadata?.form_audit) && (
        <div className="card" style={{ marginTop: "1.5rem" }}>
          <h2 style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>Form fill report</h2>
          <p style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: "0.75rem" }}>
            What the ATS asked vs what Job OS filled (page by page). CAPTCHA fields are flagged — complete
            those manually in the browser.
          </p>
          <FormFillReport audit={(lastAudit || app.metadata?.form_audit) as FormAudit} />
        </div>
      )}

      <div style={{ display: "grid", gap: "1.5rem", gridTemplateColumns: "1fr 1fr", marginTop: "1.5rem" }}>
        <div>
          <h2 style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>Tailored resume</h2>
          <div className="pre-box">{resume ?? "No resume"}</div>
        </div>
        <div>
          <h2 style={{ fontSize: "1rem", marginBottom: "0.5rem" }}>Cover letter</h2>
          <div className="pre-box">{cover ?? "No cover letter"}</div>
        </div>
      </div>
    </>
  );
}
