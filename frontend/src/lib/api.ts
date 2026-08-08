const API =
  process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL !== "/api"
    ? process.env.NEXT_PUBLIC_API_URL
    : process.env.BACKEND_URL || "http://127.0.0.1:8000";

let liveSyncPromise: Promise<{
  jobs: Job[];
  jobs_for_profile: number;
  discovered_count: number;
  by_source?: Record<string, number>;
  by_source_status?: Record<string, { last_status?: string; last_scrape_at?: string; last_result_count?: number }>;
  purged_invalid?: { jobs_rejected?: number; applications_cancelled?: number };
  purged_duplicates?: { jobs_rejected?: number; applications_cancelled?: number };
  workflow_status: string;
  message: string;
}> | null = null;

const LONG_REQUEST_TIMEOUT = 600_000;
const BOARD_SYNC_TIMEOUT = 1_200_000;

async function request<T>(path: string, init?: RequestInit, timeoutMs = 120_000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      ...init,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...init?.headers },
      cache: "no-store",
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.toLowerCase().includes("abort")) {
      throw new Error("Request timed out — this operation can take several minutes. Try again.");
    }
    throw new Error(
      msg === "Failed to fetch"
        ? "Cannot reach the API — ensure uvicorn is running on port 8000 and restart the frontend after .env changes."
        : msg,
    );
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

async function upload<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API}${path}`, { method: "POST", body: form, cache: "no-store" });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export type JobPreferences = {
  remote_only: boolean;
  internship: boolean;
  full_time: boolean;
  sponsorship: boolean;
  fresher_friendly: boolean;
  recent_days: number;
  keywords: string[];
  exclude_keywords: string[];
  experience_level: string;
  locations: string[];
  primary_city?: string;
  auto_apply_enabled: boolean;
  auto_apply_max_per_run: number;
  email_monitor_enabled: boolean;
};

export type JobFilters = {
  status?: string;
  source?: string;
  is_remote?: boolean;
  offers_sponsorship?: boolean;
  fresher_friendly?: boolean;
  internship?: boolean;
  recent_days?: number;
  keyword?: string;
};

export type ApplicationAnswers = {
  demographics?: Record<string, string>;
  compensation?: Record<string, string | number | boolean>;
  company_screening?: Record<string, string>;
  availability?: Record<string, string>;
  work_authorization_answers?: Record<string, string>;
  how_did_you_hear?: string;
  custom_answers?: Record<string, string>;
};

export type Profile = {
  full_name: string;
  email: string;
  headline?: string;
  summary?: string;
  experience_type?: string;
  skills: string[];
  projects: { name: string; description: string }[];
  employment?: { company: string; title: string; period: string }[];
  application_answers?: ApplicationAnswers;
};

export type Job = {
  id: string;
  title: string;
  company_name: string | null;
  url: string;
  source: string;
  is_remote: boolean;
  offers_sponsorship: boolean | null;
  fresher_friendly: boolean | null;
  strategy_score: number | null;
  eligibility_score: number | null;
  status: string;
  reject_reasons?: string[];
  discovered_at?: string | null;
  posted_at?: string | null;
  match_score?: number | null;
  also_on?: string[];
  board_label?: string | null;
};

export type Application = {
  id: string;
  job_id: string;
  status: string;
  approval_status: string;
  outcome: string | null;
  outcome_at?: string | null;
  rejection_reason?: string | null;
  notes?: string | null;
  job_title: string | null;
  company_name: string | null;
  job_url: string | null;
  metadata: Record<string, unknown>;
};

export type EmailMessage = {
  id: string;
  subject: string;
  from_address: string;
  body_preview: string | null;
  received_at: string | null;
  classified_outcome: string | null;
  company_name: string | null;
  rejection_reason: string | null;
  is_walk_in: boolean;
  is_interview: boolean;
};

export type Workflow = {
  id: string;
  workflow_type: string;
  status: string;
  steps: { step_id: string; agent_name: string; status: string }[];
};

export type RejectionAnalytics = {
  total_rejections: number;
  themes: Record<string, number>;
  suggestions: string[];
  profile_fixes: Record<string, unknown>;
};

export type EventRow = {
  id: string;
  event_type: string;
  source: string;
  severity: string;
  workflow_id: string | null;
  step_id: string | null;
  agent_name: string | null;
  correlation_id: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type CredentialsPayload = {
  gmail_address?: string | null;
  gmail_app_password?: string | null;
  linkedin_email?: string | null;
  linkedin_password?: string | null;
  wellfound_email?: string | null;
  wellfound_password?: string | null;
  gemini_api_key?: string | null;
};

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== "") p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `?${s}` : "";
}

export const api = {
  health: () => request<{ status: string }>("/health"),
  profile: () => request<Profile>("/profile"),
  profileCredentials: () =>
    request<CredentialsPayload & { masked?: Record<string, string | null> }>("/profile/credentials"),
  updateProfileCredentials: (payload: CredentialsPayload) =>
    request<{ message: string; saved: Record<string, string | null> }>("/profile/credentials", {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  applicationAnswers: () => request<ApplicationAnswers>("/profile/application-answers"),
  updateApplicationAnswers: (answers: ApplicationAnswers) =>
    request<{ application_answers: ApplicationAnswers; message: string }>("/profile/application-answers", {
      method: "PUT",
      body: JSON.stringify(answers),
    }),
  preferences: () => request<JobPreferences>("/preferences"),
  updatePreferences: (prefs: Partial<JobPreferences>) =>
    request<JobPreferences>("/preferences", {
      method: "PUT",
      body: JSON.stringify(prefs),
    }),
  jobs: (filters: JobFilters = {}) =>
    request<Job[]>(`/jobs${qs({ limit: 200, ...filters })}`),
  recommendedJobs: (filters: JobFilters = {}, fetch_live = false) =>
    request<Job[]>(
      `/jobs/recommended${qs({ recent_days: filters.recent_days ?? 3, dedupe: true, fetch_live, ...filters })}`,
      undefined,
      fetch_live ? 600_000 : 120_000,
    ),
  /** Fetch new postings from boards, then return profile-matched jobs (deduped in-flight). */
  syncLiveJobs: (filters: JobFilters = {}) => {
    if (liveSyncPromise) return liveSyncPromise;

    const query = qs({ recent_days: filters.recent_days ?? 3, ...filters });
    const run = async () => {
      try {
        return await request<{
          jobs: Job[];
          jobs_for_profile: number;
          discovered_count: number;
          by_source?: Record<string, number>;
          by_source_status?: Record<string, { last_status?: string; last_scrape_at?: string; last_result_count?: number }>;
          purged_invalid?: { jobs_rejected?: number; applications_cancelled?: number };
          purged_duplicates?: { jobs_rejected?: number; applications_cancelled?: number };
          workflow_status: string;
          message: string;
        }>(`/jobs/sync-live${query}`, { method: "POST" }, 600_000);
      } catch {
        const jobs = await request<Job[]>(
          `/jobs/recommended${qs({ recent_days: filters.recent_days ?? 3, dedupe: true, fetch_live: true, ...filters })}`,
          undefined,
          600_000,
        );
        return {
          jobs,
          jobs_for_profile: jobs.length,
          discovered_count: 0,
          by_source: {},
          by_source_status: {},
          purged_invalid: { jobs_rejected: 0, applications_cancelled: 0 },
          purged_duplicates: { jobs_rejected: 0, applications_cancelled: 0 },
          workflow_status: "completed",
          message: `Live sync complete — ${jobs.length} roles match your profile.`,
        };
      }
    };

    liveSyncPromise = run().finally(() => {
      liveSyncPromise = null;
    });
    return liveSyncPromise;
  },
  purgeInvalidJobs: () =>
    request<{ jobs_rejected: number; applications_cancelled: number; message: string }>(
      "/jobs/purge-invalid",
      { method: "POST" },
    ),
  discoverGlobalJobs: () =>
    request<{ workflow_id: string; status: string; message: string; jobs_for_profile?: number }>(
      "/jobs/discover-global",
      { method: "POST" },
      BOARD_SYNC_TIMEOUT,
    ),
  jobBoards: () =>
    request<{ boards: Record<string, string>; email_note: string }>("/jobs/boards"),
  cleanupApplications: () =>
    request<{ duplicates_cancelled: number; cancelled_irrelevant: number }>(
      "/applications/cleanup",
      { method: "POST" },
    ),
  applications: (params?: { approval_status?: string; outcome?: string; status?: string }) =>
    request<Application[]>(`/applications${qs({ limit: 100, ...params })}`),
  application: (id: string) => request<Application>(`/applications/${id}`),
  resume: (id: string) => request<{ content_text: string }>(`/applications/${id}/resume`),
  coverLetter: (id: string) =>
    request<{ content_text: string }>(`/applications/${id}/cover-letter`),
  runWorkflow: (workflow_type: string, context?: Record<string, unknown>) =>
    request<Workflow>(
      "/workflows",
      {
        method: "POST",
        body: JSON.stringify({ workflow_type, context }),
      },
      workflow_type === "daily_discovery" ? BOARD_SYNC_TIMEOUT : LONG_REQUEST_TIMEOUT,
    ),
  autoApply: (dryRun?: boolean) =>
    request<Workflow>("/workflows", {
      method: "POST",
      body: JSON.stringify({
        workflow_type: "auto_apply_all",
        mode: "autonomous",
        context: { auto_apply: true, dry_run: dryRun },
      }),
    }),
  approve: (id: string) =>
    request<Application>(`/applications/${id}/approve`, { method: "POST" }),
  submit: (id: string, dry_run = true) =>
    request<Record<string, unknown>>(`/applications/${id}/submit`, {
      method: "POST",
      body: JSON.stringify({ dry_run }),
    }),
  ingestResume: () =>
    request<{ message: string; full_name: string }>("/profile/ingest-resume", {
      method: "POST",
    }),
  uploadResume: (file: File) => upload<{ message: string; full_name: string }>("/profile/upload-resume", file),
  uploadCoverLetter: (file: File) =>
    upload<{ message: string; filename: string }>("/profile/upload-cover-letter", file),
  emailMessages: (outcome?: string) =>
    request<EmailMessage[]>(`/email/messages${qs({ limit: 100, outcome })}`),
  syncEmail: () =>
    request<{
      workflow_id?: string;
      status: string;
      synced?: number;
      reclassified?: number;
      error?: string;
    }>("/email/sync", { method: "POST" }, LONG_REQUEST_TIMEOUT),
  reclassifyEmails: () =>
    request<{ reclassified: number; by_outcome: Record<string, number> }>(
      "/email/reclassify",
      { method: "POST" },
      LONG_REQUEST_TIMEOUT,
    ),
  emailStats: () => request<{ total: number; by_outcome: Record<string, number> }>("/email/stats"),
  emailStatus: () =>
    request<{ configured: boolean; connected: boolean; address: string | null; error: string | null }>(
      "/email/status",
    ),
  events: (limit = 120) => request<EventRow[]>(`/events${qs({ limit })}`),
  approveAllAndApply: (dry_run = true) =>
    request<{
      approved_count: number;
      duplicates_cancelled?: number;
      cancelled_irrelevant?: number;
      apply_ok?: number;
      apply_skipped?: number;
      apply_failed?: number;
      apply_results?: any[];
      status: string;
      dry_run: boolean;
    }>(
      "/applications/approve-all-and-apply",
      {
        method: "POST",
        body: JSON.stringify({ dry_run, approve_pending: true }),
      },
      360_000,
    ),
  rejectionAnalytics: () => request<RejectionAnalytics>("/analytics/rejections"),
};
