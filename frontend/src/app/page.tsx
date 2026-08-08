"use client";

import { useCallback, useEffect, useState } from "react";
import { StatsSkeleton } from "@/components/Loading";
import { api } from "@/lib/api";

export default function DashboardPage() {
  const [showIntro, setShowIntro] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loading, setLoading] = useState(false);
  const [autoLoading, setAutoLoading] = useState(false);
  const [dryRun, setDryRun] = useState(true);
  const [msg, setMsg] = useState<{ type: "ok" | "err"; text: string } | null>(null);
  const [stats, setStats] = useState<{
    api: boolean;
    email: boolean;
    jobs: number;
    apps: number;
    pending: number;
    rejected: number;
    interviews: number;
  } | null>(null);

  const refresh = useCallback(async (silent = false) => {
    if (!silent) setPageLoading(true);
    try {
      await api.health();
      const [jobs, apps, emailSt, rejected, interviews] = await Promise.all([
        api.recommendedJobs({ recent_days: 3 }).catch(() => api.jobs({ recent_days: 3 })),
        api.applications(),
        api.emailStatus().catch(() => ({ configured: false, connected: false, address: null, error: null })),
        api.applications({ outcome: "rejected" }).catch(() => []),
        api.applications({ outcome: "interview_request" }).catch(() => []),
      ]);
      const pending = apps.filter((a) => a.approval_status === "pending").length;
      setStats({
        api: true,
        email: Boolean(emailSt.connected),
        jobs: jobs.length,
        apps: apps.length,
        pending,
        rejected: rejected.length,
        interviews: interviews.length,
      });
    } catch {
      setStats({ api: false, email: false, jobs: 0, apps: 0, pending: 0, rejected: 0, interviews: 0 });
    } finally {
      setPageLoading(false);
    }
  }, []);

  useEffect(() => {
    try {
      const seen = window.localStorage.getItem("jobos_intro_seen");
      if (!seen) {
        setShowIntro(true);
      }
    } catch {
      setShowIntro(true);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function closeIntro() {
    try {
      window.localStorage.setItem("jobos_intro_seen", "1");
    } catch {
      // Best-effort only.
    }
    setShowIntro(false);
  }

  async function runDiscovery() {
    setLoading(true);
    setMsg(null);
    try {
      const wf = await api.runWorkflow("daily_discovery");
      setMsg({
        type: "ok",
        text: `Discovery finished: ${wf.status} (${wf.steps.filter((s) => s.status === "completed").length}/${wf.steps.length} steps)`,
      });
      await refresh(true);
    } catch (e) {
      setMsg({ type: "err", text: e instanceof Error ? e.message : "Failed" });
    } finally {
      setLoading(false);
    }
  }

  async function runAutoApply() {
    setAutoLoading(true);
    setMsg(null);
    try {
      const wf = await api.autoApply(dryRun);
      setMsg({
        type: "ok",
        text: `Auto-apply ${dryRun ? "(dry-run) " : ""}finished: ${wf.status}. Check Applications & Inbox.`,
      });
      await refresh(true);
    } catch (e) {
      setMsg({ type: "err", text: e instanceof Error ? e.message : "Auto-apply failed" });
    } finally {
      setAutoLoading(false);
    }
  }

  async function syncEmail() {
    setLoading(true);
    try {
      const r = await api.syncEmail();
      setMsg({ type: "ok", text: r.error ? r.error : `Email sync: ${r.status}` });
      await refresh(true);
    } catch (e) {
      setMsg({ type: "err", text: e instanceof Error ? e.message : "Email sync failed" });
    } finally {
      setLoading(false);
    }
  }

  if (pageLoading && !stats) {
    return (
      <>
        <h1 className="page-title">Job OS Dashboard</h1>
        <p className="page-sub">Loading dashboard...</p>
        <StatsSkeleton />
      </>
    );
  }

  return (
    <>
      {showIntro && (
        <section className="intro-overlay" role="dialog" aria-modal="true" aria-label="Job OS intro">
          <div className="intro-glass">
            <p className="intro-kicker">Welcome</p>
            <h2>Job OS</h2>
            <p className="intro-text">
              A job-search operating system for software roles that discovers fresh opportunities,
              filters noise, and helps you apply faster with safer automation.
            </p>
            <ul className="intro-list">
              <li>1. Open Profile and add resume plus credentials.</li>
              <li>2. Run Discover jobs for fresh postings.</li>
              <li>3. Review Jobs and Applications, then auto-apply in dry-run first.</li>
              <li>4. Sync Inbox to track responses and improve strategy.</li>
            </ul>
            <div className="intro-actions">
              <button className="btn btn-primary" onClick={closeIntro}>Enter Dashboard</button>
            </div>
          </div>
        </section>
      )}

      <h1 className="page-title">Job OS Dashboard</h1>
      <p className="page-sub">
        Discover global jobs → filter → auto-apply → track replies from your inbox
      </p>

      {msg && (
        <div className={`alert alert-${msg.type === "ok" ? "success" : "error"}`}>{msg.text}</div>
      )}

      <div className="actions">
        <button className="btn btn-primary" onClick={runDiscovery} disabled={loading || autoLoading || pageLoading}>
          {loading ? "Running…" : "Discover jobs"}
        </button>
        <button className="btn btn-success" onClick={runAutoApply} disabled={loading || autoLoading || pageLoading}>
          {autoLoading ? "Auto-applying…" : "Auto Apply All"}
        </button>
        <label className="filter-check" style={{ alignSelf: "center" }}>
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          Dry-run (fill forms, don&apos;t submit)
        </label>
        <button className="btn btn-secondary" onClick={syncEmail} disabled={loading || pageLoading || !stats?.email}>
          {loading ? "Syncing…" : "Sync inbox"}
        </button>
        <button className="btn btn-secondary" onClick={() => refresh()} disabled={pageLoading}>
          Refresh
        </button>
      </div>

      {pageLoading ? (
        <StatsSkeleton />
      ) : (
        <div className="grid">
          <div className="card">
            <h3>API</h3>
            <div className="value">
              <span className={`status-dot ${stats?.api ? "ok" : "down"}`} />
              {stats?.api ? "Online" : "Offline"}
            </div>
          </div>
          <div className="card">
            <h3>Gmail</h3>
            <div className="value" style={{ fontSize: "1rem" }}>
              <span className={`status-dot ${stats?.email ? "ok" : "down"}`} />
              {stats?.email ? "Connected" : "Not connected"}
            </div>
          </div>
          <div className="card">
            <h3>Ranked jobs</h3>
            <div className="value">{stats?.jobs ?? 0}</div>
          </div>
          <div className="card">
            <h3>Applications</h3>
            <div className="value">{stats?.apps ?? 0}</div>
          </div>
          <div className="card">
            <h3>Pending approval</h3>
            <div className="value">{stats?.pending ?? 0}</div>
          </div>
          <div className="card">
            <h3>Rejections</h3>
            <div className="value">{stats?.rejected ?? 0}</div>
          </div>
          <div className="card">
            <h3>Interviews</h3>
            <div className="value">{stats?.interviews ?? 0}</div>
          </div>
        </div>
      )}

      <div className="card">
        <h3 style={{ marginBottom: "0.75rem", color: "var(--text)", fontSize: "1rem" }}>
          How it works
        </h3>
        <ol style={{ paddingLeft: "1.25rem", color: "var(--muted)", fontSize: "0.875rem" }}>
          <li>Upload resume on Profile — Job OS re-matches jobs to your skills</li>
          <li>Set filters on Jobs (remote, internship, sponsorship, recent)</li>
          <li>Discover jobs → Auto Apply All (tailors resume + cover letter per job)</li>
          <li>Gmail monitors replies — rejections analyzed, walk-ins flagged</li>
          <li>Review Applications for status, rejection reasons & AI fix suggestions</li>
        </ol>
      </div>
    </>
  );
}
