"use client";

import { useEffect, useRef, useState } from "react";
import { PageLoader, ProfileSkeleton } from "@/components/Loading";
import { api, type ApplicationAnswers, type CredentialsPayload, type Profile } from "@/lib/api";

const SALARY_PRESETS: Record<
  string,
  { label: string; usd: string; lpa: string; hint: string }
> = {
  conservative_intern: {
    label: "Conservative (intern / new grad)",
    usd: "40000",
    lpa: "5",
    hint: "Safer for high-volume apply; less likely to be filtered as overqualified.",
  },
  balanced_intern: {
    label: "Balanced (recommended)",
    usd: "45000",
    lpa: "6",
    hint: "Good default for B.E. + internship, remote/global roles.",
  },
  india_fresher: {
    label: "India fresher (6–8 LPA)",
    usd: "48000",
    lpa: "7",
    hint: "Typical India campus / fresher band.",
  },
  us_remote: {
    label: "US remote junior",
    usd: "55000",
    lpa: "8",
    hint: "Slightly higher; still reasonable for junior SWE.",
  },
};

const HEAR_ABOUT_OPTIONS = [
  "LinkedIn",
  "Indeed",
  "Naukri",
  "Company website",
  "Job board",
  "Referral",
  "University career fair",
  "Other",
];

const START_OPTIONS = [
  { value: "0", label: "Immediately (0 days)" },
  { value: "7", label: "1 week" },
  { value: "14", label: "2 weeks" },
  { value: "30", label: "30 days" },
];

export default function ProfilePage() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [answers, setAnswers] = useState<ApplicationAnswers | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [savingAnswers, setSavingAnswers] = useState(false);
  const [savingCreds, setSavingCreds] = useState(false);
  const [creds, setCreds] = useState<CredentialsPayload>({});
  const resumeRef = useRef<HTMLInputElement>(null);
  const coverRef = useRef<HTMLInputElement>(null);

  function load() {
    setLoading(true);
    Promise.all([
      api.profile(),
      api.applicationAnswers().catch(() => ({} as ApplicationAnswers)),
      api.profileCredentials().catch(() => ({} as CredentialsPayload)),
    ])
      .then(([p, a, c]) => {
        setProfile(p);
        setAnswers(a);
        setCreds({
          gmail_address: c.gmail_address || "",
          gmail_app_password: c.gmail_app_password || "",
          linkedin_email: c.linkedin_email || "",
          linkedin_password: c.linkedin_password || "",
          wellfound_email: c.wellfound_email || "",
          wellfound_password: c.wellfound_password || "",
          gemini_api_key: c.gemini_api_key || "",
        });
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    load();
  }, []);

  async function reingest() {
    setActionLoading(true);
    setMsg(null);
    try {
      const r = await api.ingestResume();
      setMsg(r.message);
      load();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Ingest failed");
    } finally {
      setActionLoading(false);
    }
  }

  async function onResumeUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setActionLoading(true);
    setMsg(null);
    try {
      const r = await api.uploadResume(file);
      setMsg(`${r.message} — run Discover jobs to find new matches.`);
      load();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setActionLoading(false);
      if (resumeRef.current) resumeRef.current.value = "";
    }
  }

  async function onCoverUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setActionLoading(true);
    try {
      const r = await api.uploadCoverLetter(file);
      setMsg(r.message);
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setActionLoading(false);
      if (coverRef.current) coverRef.current.value = "";
    }
  }

  if (loading && !profile) {
    return (
      <>
        <h1 className="page-title">Profile</h1>
        <p className="page-sub">Loading your profile…</p>
        <PageLoader label="Fetching resume & skills from API…" />
        <ProfileSkeleton />
      </>
    );
  }

  if (!profile) {
    return (
      <>
        <h1 className="page-title">Profile</h1>
        <div className="alert alert-error">Could not load profile. Is the API running?</div>
      </>
    );
  }

  return (
    <>
      <h1 className="page-title">Profile</h1>
      <p className="page-sub">
        Recent graduate · internship experience only — upload a new resume anytime to re-match jobs
      </p>

      <div className="actions">
        <label className="btn btn-primary" style={{ cursor: actionLoading ? "wait" : "pointer", opacity: actionLoading ? 0.6 : 1 }}>
          {actionLoading ? "Uploading…" : "Upload resume (PDF)"}
          <input ref={resumeRef} type="file" accept=".pdf" hidden onChange={onResumeUpload} disabled={actionLoading} />
        </label>
        <label className="btn btn-secondary" style={{ cursor: actionLoading ? "wait" : "pointer", opacity: actionLoading ? 0.6 : 1 }}>
          Upload cover letter
          <input ref={coverRef} type="file" accept=".pdf,.txt,.md,.doc,.docx" hidden onChange={onCoverUpload} disabled={actionLoading} />
        </label>
        <button className="btn btn-secondary" onClick={reingest} disabled={actionLoading}>
          {actionLoading ? "Working…" : "Re-ingest from resume/ folder"}
        </button>
      </div>

      {msg && <div className="alert alert-info">{msg}</div>}

      <div className="grid">
        <div className="card">
          <h3>Name</h3>
          <p>{profile.full_name}</p>
          <p style={{ color: "var(--muted)", fontSize: "0.875rem" }}>{profile.email}</p>
          {profile.headline && (
            <p style={{ marginTop: "0.5rem", fontSize: "0.875rem" }}>{profile.headline}</p>
          )}
          {profile.summary && (
            <p style={{ marginTop: "0.5rem", fontSize: "0.8rem", color: "var(--muted)" }}>
              {profile.summary}
            </p>
          )}
        </div>
        <div className="card">
          <h3>Experience</h3>
          <p style={{ fontSize: "0.875rem" }}>{profile.experience_type?.replace(/_/g, " ") || "Recent graduate"}</p>
          {profile.employment?.map((e) => (
            <p key={e.company} style={{ fontSize: "0.8rem", marginTop: "0.35rem" }}>
              <strong>{e.title}</strong> @ {e.company} ({e.period})
            </p>
          ))}
        </div>
        <div className="card">
          <h3>Skills ({profile.skills.length})</h3>
          <p style={{ fontSize: "0.875rem" }}>{profile.skills.join(", ")}</p>
        </div>
        <div className="card">
          <h3>Projects</h3>
          <ul style={{ paddingLeft: "1.25rem", fontSize: "0.875rem" }}>
            {profile.projects.map((p) => (
              <li key={p.name} style={{ marginBottom: "0.5rem" }}>
                <strong>{p.name}</strong> — {p.description}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="card" style={{ marginTop: "1.5rem" }}>
        <h3>Connector credentials</h3>
        <p style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: "1rem" }}>
          Save Gmail, LinkedIn, Wellfound, and Gemini credentials for runtime sync.
        </p>
        <form
          className="profile-form"
          onSubmit={async (e) => {
            e.preventDefault();
            setSavingCreds(true);
            setMsg(null);
            try {
              const payload: CredentialsPayload = {
                gmail_address: creds.gmail_address ?? "",
                linkedin_email: creds.linkedin_email ?? "",
                wellfound_email: creds.wellfound_email ?? "",
              };
              if ((creds.gmail_app_password || "").trim()) {
                payload.gmail_app_password = creds.gmail_app_password;
              }
              if ((creds.linkedin_password || "").trim()) {
                payload.linkedin_password = creds.linkedin_password;
              }
              if ((creds.wellfound_password || "").trim()) {
                payload.wellfound_password = creds.wellfound_password;
              }
              if ((creds.gemini_api_key || "").trim()) {
                payload.gemini_api_key = creds.gemini_api_key;
              }

              const r = await api.updateProfileCredentials(payload);
              setMsg(r.message);
            } catch (err) {
              setMsg(err instanceof Error ? err.message : "Credentials save failed");
            } finally {
              setSavingCreds(false);
            }
          }}
        >
          <label>
            <span style={{ fontSize: "0.8rem" }}>Gmail address</span>
            <input
              className="input"
              value={String(creds.gmail_address ?? "")}
              onChange={(e) => setCreds({ ...creds, gmail_address: e.target.value })}
            />
          </label>
          <label>
            <span style={{ fontSize: "0.8rem" }}>Gmail app password</span>
            <input
              className="input"
              type="password"
              placeholder="Leave blank to keep current"
              value={String(creds.gmail_app_password ?? "")}
              onChange={(e) => setCreds({ ...creds, gmail_app_password: e.target.value })}
            />
            <span className="field-note">Saved on this device only. Leave blank to keep the current password.</span>
          </label>
          <label>
            <span style={{ fontSize: "0.8rem" }}>LinkedIn email</span>
            <input
              className="input"
              value={String(creds.linkedin_email ?? "")}
              onChange={(e) => setCreds({ ...creds, linkedin_email: e.target.value })}
            />
          </label>
          <label>
            <span style={{ fontSize: "0.8rem" }}>LinkedIn password</span>
            <input
              className="input"
              type="password"
              placeholder="Leave blank to keep current"
              value={String(creds.linkedin_password ?? "")}
              onChange={(e) => setCreds({ ...creds, linkedin_password: e.target.value })}
            />
            <span className="field-note">Saved on this device only. Leave blank to keep the current password.</span>
          </label>
          <label>
            <span style={{ fontSize: "0.8rem" }}>Wellfound email</span>
            <input
              className="input"
              value={String(creds.wellfound_email ?? "")}
              onChange={(e) => setCreds({ ...creds, wellfound_email: e.target.value })}
            />
          </label>
          <label>
            <span style={{ fontSize: "0.8rem" }}>Wellfound password</span>
            <input
              className="input"
              type="password"
              placeholder="Leave blank to keep current"
              value={String(creds.wellfound_password ?? "")}
              onChange={(e) => setCreds({ ...creds, wellfound_password: e.target.value })}
            />
            <span className="field-note">Saved on this device only. Leave blank to keep the current password.</span>
          </label>
          <label style={{ gridColumn: "1 / -1" }}>
            <span style={{ fontSize: "0.8rem" }}>Gemini API key</span>
            <input
              className="input"
              type="password"
              placeholder="Leave blank to keep current"
              value={String(creds.gemini_api_key ?? "")}
              onChange={(e) => setCreds({ ...creds, gemini_api_key: e.target.value })}
            />
            <span className="field-note">Used for email classification and ranking. Leave blank to keep the current key.</span>
          </label>
          <div style={{ gridColumn: "1 / -1", display: "flex", gap: "0.75rem" }}>
            <button className="btn btn-primary" type="submit" disabled={savingCreds}>
              {savingCreds ? "Saving..." : "Save credentials"}
            </button>
          </div>
        </form>
      </div>

      {answers && (
        <div className="card" style={{ marginTop: "1.5rem" }}>
          <h3>Application questionnaire</h3>
          <p style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: "1rem" }}>
            Pre-fills Greenhouse, Lever, Workday, and similar ATS forms (salary, EEO, veteran, company
            screening). Used on Dry-run and Real submit — CAPTCHA still requires you in the browser.
          </p>
          <form
            className="profile-form"
            onSubmit={async (e) => {
              e.preventDefault();
              setSavingAnswers(true);
              setMsg(null);
              try {
                const r = await api.updateApplicationAnswers(answers);
                setAnswers(r.application_answers);
                setMsg(r.message);
              } catch (err) {
                setMsg(err instanceof Error ? err.message : "Save failed");
              } finally {
                setSavingAnswers(false);
              }
            }}
          >
            <label style={{ gridColumn: "1 / -1" }}>
              <span style={{ fontSize: "0.8rem" }}>Salary preset (fills USD + LPA below)</span>
              <select
                className="input"
                value={String(answers.compensation?.salary_preset ?? "balanced_intern")}
                onChange={(e) => {
                  const preset = SALARY_PRESETS[e.target.value];
                  if (!preset) return;
                  setAnswers({
                    ...answers,
                    compensation: {
                      ...answers.compensation,
                      salary_preset: e.target.value,
                      desired_salary_usd_annual: preset.usd,
                      expected_ctc_lpa: preset.lpa,
                    },
                  });
                }}
              >
                {Object.entries(SALARY_PRESETS).map(([k, p]) => (
                  <option key={k} value={k}>
                    {p.label} — ${p.usd}/yr · {p.lpa} LPA
                  </option>
                ))}
              </select>
              <p style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "0.35rem" }}>
                {SALARY_PRESETS[String(answers.compensation?.salary_preset ?? "balanced_intern")]
                  ?.hint ||
                  "Pick a preset, then tweak numbers if needed. Too high can get auto-rejected; too low can undervalue you."}
              </p>
            </label>
            <label>
              <span style={{ fontSize: "0.8rem" }}>Desired salary (USD / year)</span>
              <input
                className="input"
                type="number"
                min={30000}
                max={120000}
                value={String(answers.compensation?.desired_salary_usd_annual ?? "")}
                onChange={(e) =>
                  setAnswers({
                    ...answers,
                    compensation: {
                      ...answers.compensation,
                      desired_salary_usd_annual: e.target.value,
                    },
                  })
                }
              />
            </label>
            <label>
              <span style={{ fontSize: "0.8rem" }}>Expected CTC (LPA, India)</span>
              <input
                className="input"
                type="number"
                min={3}
                max={15}
                step={0.5}
                value={String(answers.compensation?.expected_ctc_lpa ?? "")}
                onChange={(e) =>
                  setAnswers({
                    ...answers,
                    compensation: { ...answers.compensation, expected_ctc_lpa: e.target.value },
                  })
                }
              />
            </label>
            <label>
              <span style={{ fontSize: "0.8rem" }}>Gender</span>
              <select
                className="input"
                value={answers.demographics?.gender ?? "Male"}
                onChange={(e) =>
                  setAnswers({
                    ...answers,
                    demographics: { ...answers.demographics, gender: e.target.value },
                  })
                }
              >
                <option>Male</option>
                <option>Female</option>
                <option>Non-binary</option>
                <option>Prefer not to say</option>
              </select>
            </label>
            <label>
              <span style={{ fontSize: "0.8rem" }}>Protected veteran status</span>
              <select
                className="input"
                value={answers.demographics?.veteran_status ?? ""}
                onChange={(e) =>
                  setAnswers({
                    ...answers,
                    demographics: { ...answers.demographics, veteran_status: e.target.value },
                  })
                }
              >
                <option>I am not a protected veteran</option>
                <option>I identify as one or more of the classifications of protected veteran</option>
                <option>Prefer not to say</option>
              </select>
            </label>
            <label>
              <span style={{ fontSize: "0.8rem" }}>Disability status</span>
              <select
                className="input"
                value={answers.demographics?.disability_status ?? ""}
                onChange={(e) =>
                  setAnswers({
                    ...answers,
                    demographics: { ...answers.demographics, disability_status: e.target.value },
                  })
                }
              >
                <option>No, I do not have a disability</option>
                <option>Yes, I have a disability</option>
                <option>Prefer not to say</option>
              </select>
            </label>
            <label>
              <span style={{ fontSize: "0.8rem" }}>Requires visa sponsorship</span>
              <select
                className="input"
                value={answers.work_authorization_answers?.requires_visa_sponsorship ?? "Yes"}
                onChange={(e) =>
                  setAnswers({
                    ...answers,
                    work_authorization_answers: {
                      ...answers.work_authorization_answers,
                      requires_visa_sponsorship: e.target.value,
                    },
                  })
                }
              >
                <option>Yes</option>
                <option>No</option>
              </select>
            </label>
            <label>
              <span style={{ fontSize: "0.8rem" }}>Previously employed at this company</span>
              <select
                className="input"
                value={answers.company_screening?.previously_employed_at_company ?? "No"}
                onChange={(e) =>
                  setAnswers({
                    ...answers,
                    company_screening: {
                      ...answers.company_screening,
                      previously_employed_at_company: e.target.value,
                    },
                  })
                }
              >
                <option>No</option>
                <option>Yes</option>
              </select>
            </label>
            <label>
              <span style={{ fontSize: "0.8rem" }}>Relative employed at company</span>
              <select
                className="input"
                value={answers.company_screening?.relative_employed_at_company ?? "No"}
                onChange={(e) =>
                  setAnswers({
                    ...answers,
                    company_screening: {
                      ...answers.company_screening,
                      relative_employed_at_company: e.target.value,
                    },
                  })
                }
              >
                <option>No</option>
                <option>Yes</option>
              </select>
            </label>
            <label>
              <span style={{ fontSize: "0.8rem" }}>How soon can you join?</span>
              <select
                className="input"
                value={answers.availability?.notice_period_days ?? "0"}
                onChange={(e) => {
                  const days = e.target.value;
                  const label =
                    START_OPTIONS.find((o) => o.value === days)?.label.split(" (")[0] || "Immediate";
                  setAnswers({
                    ...answers,
                    availability: {
                      ...answers.availability,
                      notice_period_days: days,
                      start_date: days === "0" ? "Immediate" : label,
                    },
                  });
                }}
              >
                {START_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <p style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "0.35rem" }}>
                Forms asking for a number of days get <strong>0</strong> for immediate; text fields get
                &quot;Immediate&quot;.
              </p>
            </label>
            <label>
              <span style={{ fontSize: "0.8rem" }}>How did you hear about us</span>
              <select
                className="input"
                value={
                  answers.how_did_you_hear &&
                  HEAR_ABOUT_OPTIONS.includes(answers.how_did_you_hear)
                    ? answers.how_did_you_hear
                    : "Other"
                }
                onChange={(e) => {
                  const v = e.target.value;
                  setAnswers({
                    ...answers,
                    how_did_you_hear: v === "Other" ? "LinkedIn" : v,
                  });
                }}
              >
                {HEAR_ABOUT_OPTIONS.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
              {(!answers.how_did_you_hear ||
                !HEAR_ABOUT_OPTIONS.includes(answers.how_did_you_hear)) && (
                <input
                  className="input"
                  style={{ marginTop: "0.35rem" }}
                  placeholder="Other (type here)"
                  value={answers.how_did_you_hear ?? ""}
                  onChange={(e) => setAnswers({ ...answers, how_did_you_hear: e.target.value })}
                />
              )}
            </label>
            <label style={{ gridColumn: "1 / -1" }}>
              <span style={{ fontSize: "0.8rem" }}>Salary notes (optional)</span>
              <textarea
                className="input"
                rows={2}
                value={String(answers.compensation?.salary_notes ?? "")}
                onChange={(e) =>
                  setAnswers({
                    ...answers,
                    compensation: { ...answers.compensation, salary_notes: e.target.value },
                  })
                }
              />
            </label>
            <div style={{ gridColumn: "1 / -1" }}>
              <button type="submit" className="btn btn-primary" disabled={savingAnswers}>
                {savingAnswers ? "Saving…" : "Save questionnaire"}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
