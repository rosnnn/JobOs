"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { OpaqueScreenLoader, Spinner, TableSkeleton } from "@/components/Loading";
import { api, type JobFilters, type JobPreferences } from "@/lib/api";

function decodeHtmlEntities(text: string): string {
  if (!text) return text;
  return text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(Number(n)));
}

const SOURCES = [
  "jsearch",
  "adzuna_in",
  "adzuna_us",
  "adzuna_gb",
  "adzuna_au",
  "adzuna_ca",
  "adzuna_de",
  "adzuna_sg",
  "remoteok",
  "remotive",
  "jobicy",
  "arbeitnow",
  "weworkremotely",
  "jobspresso",
  "startup_jobs",
  "findwork",
  "greenhouse",
  "lever",
  "himalayas",
  "linkedin",
  "wellfound",
];

function buildFilterParams(filters: JobFilters, keyword: string): JobFilters {
  return {
    ...filters,
    keyword: keyword.trim() || undefined,
  };
}

function formatSourceCounts(bySource?: Record<string, number>): string {
  const pairs = Object.entries(bySource || {}).sort((a, b) => b[1] - a[1]);
  const nonZero = pairs.filter(([, count]) => count > 0);
  if (!nonZero.length) return "No new jobs from enabled sources in this run.";
  return nonZero
    .slice(0, 8)
    .map(([src, count]) => `${src}:${count}`)
    .join(" | ");
}

function formatBoardStatus(status?: Record<string, { last_status?: string; last_scrape_at?: string; last_result_count?: number }>): string {
  const linkedIn = status?.linkedin?.last_status || "unknown";
  const wellfound = status?.wellfound?.last_status || "unknown";
  return `linkedin:${linkedIn} | wellfound:${wellfound}`;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Awaited<ReturnType<typeof api.jobs>>>([]);
  const [prefs, setPrefs] = useState<JobPreferences | null>(null);
  const [filters, setFilters] = useState<JobFilters>({ recent_days: 3 });
  const [keyword, setKeyword] = useState("");
  const [profileMode, setProfileMode] = useState(true);
  const [boardNote, setBoardNote] = useState<string | null>(null);
  const [discoverMsg, setDiscoverMsg] = useState<string | null>(null);
  const [discovering, setDiscovering] = useState(false);
  const [fetchingLive, setFetchingLive] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [initialDone, setInitialDone] = useState(false);
  const filtersRef = useRef({ filters, keyword, profileMode });
  filtersRef.current = { filters, keyword, profileMode };
  const liveSyncStarted = useRef(false);

  const load = useCallback(async (opts?: { fetchLive?: boolean }) => {
    const fetchLive = opts?.fetchLive ?? false;
    const { filters: f, keyword: kw, profileMode: pm } = filtersRef.current;
    const filterParams = buildFilterParams(f, kw);
    setError(null);
    setLoading(true);
    if (fetchLive && pm) setFetchingLive(true);
    try {
      const [p, boards] = await Promise.all([
        api.preferences(),
        api.jobBoards().catch(() => null),
      ]);
      setPrefs(p);
      setBoardNote(boards?.email_note ?? null);

      if (pm) {
        if (fetchLive) {
          if (liveSyncStarted.current) {
            setLoading(false);
            return;
          }
          liveSyncStarted.current = true;
          try {
            const sync = await api.syncLiveJobs(filterParams);
            setJobs(sync.jobs);
            setLastSyncedAt(new Date().toLocaleString());
            const purgedInvalid = sync.purged_invalid?.jobs_rejected ?? 0;
            const purgedDupes = sync.purged_duplicates?.jobs_rejected ?? 0;
            const sourceLine = formatSourceCounts(sync.by_source);
            const boardStatus = formatBoardStatus(sync.by_source_status);
            const headline = sync.message?.trim() || "Live sync complete.";
            setDiscoverMsg(
              `${headline} | discovered:${sync.discovered_count} matched:${sync.jobs_for_profile} invalid:${purgedInvalid} dupes:${purgedDupes} | ${sourceLine} | ${boardStatus}`,
            );
          } catch (e) {
            try {
              const cached = await api.recommendedJobs(filterParams, false);
              setJobs(cached);
            } catch {
              /* keep existing rows */
            }
            const raw = e instanceof Error ? e.message : "Live sync failed";
            setDiscoverMsg(
              raw.includes("timed out")
                ? raw
                : `Board sync failed — showing cached matches. ${raw}`,
            );
          } finally {
            setFetchingLive(false);
            liveSyncStarted.current = false;
          }
        } else {
          const cached = await api.recommendedJobs(filterParams, false);
          setJobs(cached);
        }
      } else {
        const j = await api.jobs(filterParams);
        setJobs(j);
      }
    } catch (e) {
      const raw = e instanceof Error ? e.message : "Failed to load jobs";
      let msg = raw;
      try {
        const parsed = JSON.parse(raw) as { detail?: string };
        if (parsed.detail) {
          msg =
            parsed.detail === "Method Not Allowed"
              ? "API needs a restart — stop uvicorn and run it again so /jobs/sync-live is registered."
              : parsed.detail;
        }
      } catch {
        /* not JSON */
      }
      setError(msg);
    } finally {
      setLoading(false);
      setFetchingLive(false);
      setInitialDone(true);
    }
  }, []);

  useEffect(() => {
    (async () => {
      await load({ fetchLive: false });
    })();
  }, [load]);

  useEffect(() => {
    if (!discoverMsg) return;
    const t = window.setTimeout(() => setDiscoverMsg(null), 5500);
    return () => window.clearTimeout(t);
  }, [discoverMsg]);

  function toggleFilter(key: keyof JobFilters, val: boolean | undefined) {
    setFilters((f) => ({ ...f, [key]: f[key] === val ? undefined : val }));
  }

  if (loading && !initialDone) {
    return <OpaqueScreenLoader label="Loading jobs..." />;
  }

  return (
    <>
      {loading || fetchingLive ? <OpaqueScreenLoader label="Loading jobs..." /> : null}
      <h1 className="page-title">Job Search</h1>
      <p className="page-sub">
        Jobs are fetched from all enabled boards, sorted by your resume city first, then country,
        then global remote. Use <strong>Apply filters</strong> or <strong>Fetch new jobs now</strong>.
      </p>
      {boardNote && (
        <p style={{ color: "var(--muted)", fontSize: "0.8rem", marginBottom: "1rem" }}>{boardNote}</p>
      )}

      <div className="filter-panel">
        <h3>Filters</h3>
        <div className="filter-grid">
          <label className="filter-check">
            <input
              type="checkbox"
              checked={!!filters.is_remote}
              onChange={() => toggleFilter("is_remote", true)}
            />
            Remote only
          </label>
          <label className="filter-check">
            <input
              type="checkbox"
              checked={!!filters.internship}
              onChange={() => toggleFilter("internship", true)}
            />
            Internship
          </label>
          <label className="filter-check">
            <input
              type="checkbox"
              checked={!!filters.offers_sponsorship}
              onChange={() => toggleFilter("offers_sponsorship", true)}
            />
            Visa sponsorship
          </label>
          <label className="filter-check">
            <input
              type="checkbox"
              checked={!!filters.fresher_friendly}
              onChange={() => toggleFilter("fresher_friendly", true)}
            />
            Fresher / entry level
          </label>
          <label className="filter-field">
            Posted within
            <select
              value={filters.recent_days ?? 3}
              onChange={(e) => setFilters((f) => ({ ...f, recent_days: Number(e.target.value) }))}
              disabled={loading}
            >
              <option value={1}>1 day</option>
              <option value={2}>2 days</option>
              <option value={3}>3 days</option>
            </select>
          </label>
          <label className="filter-field">
            Status
            <select
              value={filters.status ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value || undefined }))}
              disabled={loading}
            >
              <option value="">All</option>
              <option value="ranked">Ranked</option>
              <option value="qualified">Qualified</option>
              <option value="discovered">Discovered</option>
              <option value="rejected">Rejected</option>
            </select>
          </label>
          <label className="filter-field">
            Source
            <select
              value={filters.source ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, source: e.target.value || undefined }))}
              disabled={loading}
            >
              <option value="">All sources</option>
              {SOURCES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="filter-field filter-keyword">
            Keywords
            <input
              type="text"
              placeholder="backend, intern, python…"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !loading && load({ fetchLive: false })}
              disabled={loading}
            />
          </label>
        </div>
        <div className="actions" style={{ marginTop: "1rem", marginBottom: 0 }}>
          <button
            className="btn btn-primary"
            disabled={loading}
            onClick={() => load({ fetchLive: false })}
          >
            Apply filters
          </button>
          <button
            className="btn btn-success"
            disabled={discovering || loading}
            onClick={async () => {
              setDiscovering(true);
              setProfileMode(true);
              await load({ fetchLive: true });
              setDiscovering(false);
            }}
          >
            {discovering || fetchingLive ? "Fetching live…" : "Fetch new jobs now"}
          </button>
          <button
            className="btn btn-warning"
            disabled={loading}
            onClick={async () => {
              setError(null);
              setDiscoverMsg(null);
              try {
                const r = await api.purgeInvalidJobs();
                setDiscoverMsg(
                  `Removed ${r.jobs_rejected} invalid jobs · cancelled ${r.applications_cancelled} fake applications`,
                );
                await load({ fetchLive: false });
              } catch (e) {
                setError(e instanceof Error ? e.message : "Purge failed");
              }
            }}
          >
            Remove invalid jobs
          </button>
          <label className="filter-check" style={{ alignSelf: "center" }}>
            <input
              type="checkbox"
              checked={profileMode}
              onChange={(e) => setProfileMode(e.target.checked)}
            />
            Resume-matched only
          </label>
          <button
            className="btn btn-secondary"
            onClick={() => load({ fetchLive: profileMode })}
            disabled={loading}
          >
            {fetchingLive ? "Fetching from boards…" : loading ? "Updating…" : "Refresh (live fetch)"}
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => {
              setFilters({ recent_days: 3 });
              setKeyword("");
            }}
            disabled={loading}
          >
            Reset
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {discoverMsg && <div className="alert alert-success">{discoverMsg}</div>}

      {loading && !initialDone ? (
        <>
          <div className="status-line" style={{ color: "var(--muted)", fontSize: "0.875rem", marginBottom: "1rem" }}>
            <Spinner label="Loading jobs…" />
          </div>
          <TableSkeleton rows={8} cols={10} />
        </>
      ) : (
        <>
          <div className="status-line" style={{ color: "var(--muted)", fontSize: "0.875rem", marginBottom: "1rem" }}>
            {fetchingLive ? (
              <Spinner label="Fetching new jobs from all boards (city → country → global)…" />
            ) : loading ? (
              <Spinner label="Updating…" />
            ) : (
              <>
                <strong>{jobs.length}</strong> software roles (last {filters.recent_days ?? 3} days)
                {prefs?.primary_city ? ` · sorted: ${prefs.primary_city} → country → global` : ""}
                {lastSyncedAt ? ` · last live sync ${lastSyncedAt}` : ""}
              </>
            )}
          </div>

          {loading && jobs.length > 0 ? (
            <TableSkeleton rows={6} cols={10} />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Title</th>
                    <th>Company</th>
                    <th>Source</th>
                    <th>Remote</th>
                    <th>Sponsor</th>
                    <th>Intern</th>
                    <th>Match</th>
                    <th>Score</th>
                    <th>Posted (newest first)</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((j) => (
                    <tr key={j.id}>
                      <td>{decodeHtmlEntities(j.title)}</td>
                      <td>{j.company_name || "—"}</td>
                      <td title={j.also_on?.join(", ")}>
                        {j.board_label || j.source}
                        {j.also_on && j.also_on.length > 1 ? ` (+${j.also_on.length - 1})` : ""}
                      </td>
                      <td>{j.is_remote ? "✓" : "—"}</td>
                      <td>{j.offers_sponsorship ? "✓" : j.offers_sponsorship === false ? "✗" : "—"}</td>
                      <td>{/intern/i.test(j.title) ? "✓" : "—"}</td>
                      <td>{j.match_score != null ? `${Math.round(j.match_score * 100)}%` : "—"}</td>
                      <td>{j.strategy_score?.toFixed(2) ?? j.eligibility_score?.toFixed(2) ?? "—"}</td>
                      <td>
                        {j.posted_at
                          ? new Date(j.posted_at).toLocaleString()
                          : j.discovered_at
                            ? new Date(j.discovered_at).toLocaleString()
                            : "—"}
                      </td>
                      <td>
                        <a href={j.url} target="_blank" rel="noreferrer">
                          Open
                        </a>
                      </td>
                    </tr>
                  ))}
                  {jobs.length === 0 && (
                    <tr>
                      <td colSpan={10} style={{ color: "var(--muted)", textAlign: "center" }}>
                        No jobs match these filters — try Reset, widen posted-within, or Fetch new jobs now
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  );
}
