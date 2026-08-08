# Job OS — Implementation Roadmap

## Phase 1 — Foundation (Weeks 1–3) ✅ START HERE

**Goal:** Runnable platform skeleton with discovery pipeline and persistence.

- [x] Repository scaffold, Docker, config, logging
- [x] PostgreSQL schema + Alembic migrations
- [x] Event system + structured logging
- [x] Agent base class + registry
- [x] Coordinator + `daily_discovery` workflow FSM
- [x] Scout, JobDiscovery, Eligibility agents (rule + LLM hooks)
- [x] Strategy engine v0 (heuristic EV scoring)
- [x] World model read/write
- [x] Memory service (event + episodic)
- [x] FastAPI routes: health, workflows, jobs, events
- [x] Celery task stubs for scheduled runs
- [x] Browser layer interface (no full apply yet)
- [x] Sample professional identity + resume template

**Exit criteria:** `POST /workflows` runs discovery → eligibility → ranking → persists jobs; events queryable.

---

## Phase 2 — Intelligence Loop (Weeks 4–6) ✅ IN PROGRESS

**Goal:** Tailoring, reflection, and learning from outcomes.

- [x] Resume Tailoring + Cover Letter agents (truthfulness validator)
- [x] Multi-identity system fully wired with `data/resumes/*.md` templates
- [x] Reflection agent + strategy_updates pipeline
- [x] Application draft + approval queue
- [ ] pgvector embeddings for semantic memory retrieval
- [ ] Recruiter + company memory enrichment
- [ ] Improved JobDiscovery parsers per ATS (Greenhouse, Lever)

**Exit criteria:** End-to-end dry-run generates tailored docs; reflection updates world model after mock outcomes. ✅ achievable now

---

## Phase 3 — Browser Execution (Weeks 7–10) ✅ CORE SHIPPED

**Goal:** Real applications with safety gates.

- [x] Playwright session manager + artifact storage (screenshots, HTML)
- [x] FormReasoner (DOM heuristic field mapping + profile answers)
- [x] Browser Apply agent (Greenhouse/Lever/generic ATS detection)
- [x] Human approval API + per-application submit
- [x] Rate limiting (daily apply cap)
- [x] Screening answers via `user_profile.screening_answers`
- [x] Dry-run mode default (`JOB_OS_BROWSER_DRY_RUN=true`)
- [ ] Browser Use integration (optional)
- [ ] LLM form reasoning for unknown fields

**Exit criteria:** Supervised dry-run apply to 1 test job with approval; full audit trail. ✅

---

## Phase 4 — Autonomy & Scale (Weeks 11–14)

**Goal:** Daily autonomous operation with measurable improvement.

- APScheduler/Celery beat: daily_discovery cron
- Market Intelligence agent (trend feeds)
- Recruiter Intelligence agent
- Autonomous mode with confidence-gated prompt updates
- Next.js dashboard (jobs, approvals, metrics)
- Qdrant option if pgvector insufficient
- Wellfound, Remote OK, YC Jobs parsers

**Exit criteria:** 7-day supervised run with improving response-rate metrics logged.

---

## Phase 5 — Production Hardening (Weeks 15+)

- Multi-tenant user profiles
- S3/MinIO for resume/artifact storage
- Prometheus metrics + Grafana
- CI/CD, staging environment
- Chaos testing on browser flows
- A/B testing for strategy weights

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| Site structure changes | DOM reasoning, not brittle selectors; parser version tags |
| LLM hallucination on forms | Canonical profile + validator; human approval default |
| Account bans | Rate limits, realistic delays, no spam patterns |
| Legal/ToS | Supervised mode default; user owns accounts |

---

## Metrics (North Star)

- **Qualified jobs discovered / day**
- **Application → response rate** (by identity, country, source)
- **Sponsorship-tagged apply → interview rate**
- **Strategy EV calibration error** (predicted vs actual)
- **Reflection actionability score** (human-rated sample)
