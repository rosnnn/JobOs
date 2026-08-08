# Job OS — Autonomous Digital Operator Architecture

Job OS is a **persistent autonomous agent operating system** for strategic opportunity execution. The initial domain is global IT job acquisition for a fresher software engineer from India.

## Design Principles

| Principle | Implementation |
|-----------|----------------|
| Persistence | PostgreSQL as source of truth; Redis for queues/cache |
| Modularity | One agent = one module; structured I/O only |
| Observability | Every action → `events` table + structured logs |
| Safety | Intent → validation → execution → log → reflection |
| No fake autonomy | Bounded workflows, rate limits, human approval gates |
| Evolution | Reflection engine mutates strategy/prompts from outcomes |

## System Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Next.js Dashboard (Phase 4)                      │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │ REST / WebSocket
┌───────────────────────────────────▼─────────────────────────────────────┐
│  FastAPI API Layer                                                       │
│  /workflows  /jobs  /applications  /memory  /strategy  /approvals       │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼─────────────────────────────────────┐
│  Orchestration Layer                                                     │
│  Coordinator · WorkflowEngine · ApprovalGate · RateLimiter               │
└───────────────────────────────────┬─────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ Agent Runtime │         │ Memory Service  │         │ Strategy Engine │
│ (specialists) │◄───────►│ episodic/event  │◄───────►│ EV scoring      │
└───────┬───────┘         └────────┬────────┘         └────────┬────────┘
        │                          │                           │
        ▼                          ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌─────────────────┐
│ Browser Layer │         │ World Model     │         │ Reflection      │
│ Playwright    │         │ JSON state blob │         │ post-session    │
└───────────────┘         └─────────────────┘         └─────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────────────┐
│ PostgreSQL (+ pgvector)  │  Redis  │  Celery workers  │  Object storage   │
└───────────────────────────────────────────────────────────────────────────┘
```

## Repository Layout

```
AGI/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── .env.example
├── docs/
│   ├── ARCHITECTURE.md      # this file
│   ├── ROADMAP.md
│   └── AGENT_PROTOCOL.md
├── alembic/versions/
├── scripts/
│   └── init_db.py
└── src/job_os/
    ├── main.py                 # FastAPI entry
    ├── config/                 # Settings (pydantic-settings)
    ├── api/                    # HTTP routers
    ├── agents/                 # Specialist agents
    ├── orchestration/          # Coordinator, workflows, gates
    ├── memory/                 # Episodic, retrieval, embeddings hook
    ├── world_model/            # Strategic state
    ├── reflection/             # Post-session analysis
    ├── strategy/               # EV scoring, prioritization
    ├── browser/                # Playwright + Browser Use adapter
    ├── models/                 # SQLAlchemy ORM
    ├── schemas/                # Pydantic DTOs
    ├── services/               # Shared business logic
    ├── tasks/                  # Celery task definitions
    └── core/                   # Events, logging, safety, LLM clients
```

## Agent Communication Design

Agents **do not** call each other directly. All inter-agent communication flows through:

1. **Workflow context** — immutable inputs + mutable scratchpad passed by Coordinator
2. **Event bus** — append-only `events` rows (audit trail)
3. **Memory service** — read/write structured memory keys
4. **Redis streams** (optional) — real-time dashboard updates

### Message Envelope

```python
AgentMessage(
    workflow_id: UUID,
    step_id: str,
    agent_name: str,
    intent: str,           # e.g. "discover_jobs", "check_eligibility"
    payload: dict,         # structured input
    correlation_id: UUID,
)
```

### Agent Contract

Every agent implements:

```python
async def run(ctx: WorkflowContext, msg: AgentMessage) -> AgentResult:
    # validate input → execute → emit events → return structured output
```

`AgentResult` contains: `success`, `output`, `artifacts`, `memory_writes`, `next_step_hint`, `requires_approval`.

### Agent Registry

| Agent | Responsibility |
|-------|----------------|
| **Coordinator** | Workflow FSM, step dispatch, approval gates, failure recovery |
| **Scout** | Seed URLs, site health, new source discovery |
| **JobDiscovery** | Parse listings from Greenhouse/Lever/YC/Wellfound/RemoteOK |
| **Eligibility** | Hard filters: sponsorship, clearance, citizenship, fresher fit |
| **ResumeTailoring** | Identity selection + ATS keyword injection (truthful only) |
| **CoverLetter** | Role-specific cover letter generation |
| **BrowserApply** | Form reasoning, upload, screening Q&A, screenshots |
| **Reflection** | Session post-mortem, pattern extraction |
| **MarketIntelligence** | Trend ingestion, skill demand signals |
| **RecruiterIntelligence** | Recruiter graph, responsiveness scoring |
| **Strategy** | EV-based prioritization, identity choice |
| **Memory** | Consolidation, dedup, embedding index (Phase 2+) |
| **Tracking** | Application state machine, outcome ingestion |

## Orchestration Flow

### Daily Autonomous Workflow (`daily_discovery`)

```
START
  → Scout.refresh_sources()
  → JobDiscovery.discover(batch_sources)
  → Eligibility.filter(jobs)
  → Strategy.rank(jobs, world_model)
  → [HUMAN_APPROVAL if mode=supervised] select top-N
  → FOR each job:
        Strategy.pick_identity(job)
        ResumeTailoring.tailor(identity, job)
        CoverLetter.generate(job, resume)
        BrowserApply.submit() OR queue_for_approval
        Tracking.record(application)
  → Reflection.analyze_session()
  → Strategy.update_from_reflection()
  → Memory.consolidate()
END
```

### Workflow State Machine

States: `pending` → `running` → `awaiting_approval` → `completed` | `failed` | `cancelled`

Each step is idempotent via `workflow_steps` table with `idempotency_key`.

## Database Schema (Conceptual)

See `src/job_os/models/` for SQLAlchemy implementation.

**Core entities:** `jobs`, `companies`, `recruiters`, `applications`, `resumes`, `cover_letters`, `professional_identities`

**Operational:** `workflows`, `workflow_steps`, `events`, `browser_sessions`, `browser_artifacts`

**Intelligence:** `reflections`, `strategy_updates`, `market_data`, `memory_records`, `world_state`

**Safety:** `approval_requests`, `rate_limit_ledger`

## Memory Architecture

### Layers

| Layer | Storage | Content |
|-------|---------|---------|
| **Event memory** | `events` | Raw audit: every agent action |
| **Episodic memory** | `memory_records` type=episodic | Session summaries, outcomes |
| **Semantic memory** | `memory_records` type=semantic + pgvector (Phase 2) | Company patterns, rejection reasons |
| **Procedural memory** | `strategy_updates` + prompt versions | What workflows/prompts work |
| **Working memory** | `workflow_context` JSON on `workflows` | Scratchpad for active run |

### Memory Keys (examples)

- `company:{id}:rejection_patterns`
- `resume:{identity_id}:performance`
- `country:{code}:visa_friendliness`
- `source:{site}:yield_rate`

## World Model

Single row `world_state` (versioned JSONB) updated by Strategy, Reflection, MarketIntelligence:

```json
{
  "market_conditions": { "remote_ratio": 0.42, "fresher_openings_7d": 120 },
  "user_profile": { "skills": [], "experience_years": 0, "location": "IN" },
  "country_hiring_trends": { "DE": { "sponsorship_rate": 0.15 } },
  "visa_friendliness": { "CA": 0.7, "US": 0.3 },
  "resume_performance": { "backend_engineer": { "response_rate": 0.08 } },
  "skill_market_demand": { "python": 0.9, "rust": 0.6 }
}
```

Agents read world model at workflow start; Strategy/Reflection write deltas.

## Browser Architecture

```
BrowserApplyAgent
    → BrowserSessionManager (lifecycle, contexts)
    → FormReasoner (LLM + DOM snapshot, no site-specific hardcoding)
    → ActionExecutor (Playwright primitives)
    → ArtifactStore (screenshots, HTML dumps → browser_artifacts)
    → SafetyValidator (no false eligibility claims)
```

**Human approval mode:** workflow pauses at `awaiting_approval`; operator reviews screenshot + filled form via API before `BrowserApplyAgent.resume()`.

**Rate limiting:** `rate_limit_ledger` enforces max applications/day per source.

## Reflection Architecture

Triggered after workflow completion or on schedule:

1. Load session events + application outcomes
2. LLM structured extraction: failures, wins, hypotheses
3. Persist `reflections` row
4. Emit `strategy_updates` (prior weights, prompt deltas, source rankings)
5. Update `world_state` partial merge

Reflection **never** auto-applies prompt changes in autonomous mode without confidence threshold + optional human review (configurable).

## Strategy Engine

**Expected Value score** per job:

```
EV = P(response) × P(interview) × P(offer) × salary_weight
     × sponsorship_bonus × remote_bonus
     - competition_penalty - time_cost
```

Weights learned from `applications` outcomes via exponential moving average in `strategy_updates`.

**Identity selection:** argmax over `professional_identities` using resume_performance × role_fit matrix.

## API Structure

| Prefix | Purpose |
|--------|---------|
| `GET /health` | Liveness |
| `POST /workflows` | Start workflow (type, mode) |
| `GET /workflows/{id}` | Status + steps |
| `POST /workflows/{id}/approve` | Human approval |
| `GET /jobs` | List/filter discovered jobs |
| `GET /applications` | Application pipeline |
| `POST /memory/query` | Structured memory retrieval |
| `GET /strategy/world` | Current world model |
| `GET /events` | Audit log (paginated) |

## Configuration Structure

Environment-driven via `pydantic-settings`:

- `JOB_OS_MODE`: `supervised` | `autonomous`
- `JOB_OS_LLM_PROVIDER`: `openai` | `anthropic`
- LLM keys, DB URL, Redis URL
- Rate limits, approval requirements
- Target sites enable flags

## Logging Architecture

- **structlog** JSON to stdout (Docker-friendly)
- Every log includes: `workflow_id`, `agent`, `correlation_id`
- `events` table mirrors critical actions for replay/debug
- Log levels per module via config

## Safety & Risk Constraints

- `SafetyValidator` blocks: fabricated experience, false visa claims, mass-apply bursts
- Eligibility agent uses **hard rules** before LLM soft scoring
- All generated resume deltas must pass `truthfulness_check` against canonical profile
- Browser agent cannot submit without `approval_status=approved` when supervised

## Technology Choices (Rationale)

| Choice | Why |
|--------|-----|
| FastAPI | Async, OpenAPI, production standard |
| SQLAlchemy 2.0 | Typed ORM, Alembic migrations |
| Celery + Redis | Durable scheduled workflows |
| Playwright | Reliable cross-site automation |
| No LangChain | Direct LLM clients + structured outputs = less magic, more control |
| pgvector later | Keeps Phase 1 simpler; same Postgres instance |
