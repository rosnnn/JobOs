# Job OS

Job OS is an autonomous job pipeline for software roles:
- discovers jobs from multiple boards
- filters for real, relevant opportunities
- ranks by profile fit
- helps draft and track applications
- syncs inbox signals for feedback loops

## Product Screenshots

![Job OS Dashboard](Snaps/Screenshot%202026-08-07%20150133.png)
![Job OS Jobs View](Snaps/Screenshot%202026-08-07%20150203.png)
![Job OS Profile and Controls](Snaps/Screenshot%202026-08-07%20150307.png)

## What Is Implemented

- Live board sync orchestration with source diagnostics
- LinkedIn and Wellfound browser scraping hooks with cooldown status tracking
- Fresh-first job listing behavior from the current sync run
- Strict recency defaults (3 days)
- Duplicate and invalid job cleanup
- Next.js dashboard for jobs, applications, logs, inbox, profile

## Quick Start (Local)

### 1) Requirements

- Python 3.11+
- Node 20+
- PostgreSQL and Redis (or Docker)

### 2) Backend setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env
python scripts/init_db.py
uvicorn job_os.main:app --app-dir src --host 127.0.0.1 --port 8000
```

### 3) Frontend setup

```bash
cd frontend
npm install
copy .env.local.example .env.local
npm run dev -- -p 3000
```

Open: http://127.0.0.1:3000

## First-Run Usage

1. Open Profile and upload resume.
2. Save Gmail and board credentials in Profile.
3. Run Discover jobs from Dashboard.
4. Open Jobs and review fresh matches.
5. Run auto-apply in dry-run mode first.
6. Sync Inbox and inspect logs.

## Strict Freshness and Cleanup

- Recency defaults and max are set to 3 days for live sync and recommended flows.
- Invalid and duplicate jobs are purged during sync.
- Dummy listings can be removed with:

```bash
python scripts/purge_dummy_jobs.py
```

## Deploy to EC2 (Ubuntu)

Use this exact sequence on your instance:

```bash
sudo apt update && sudo apt install -y git docker.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker

cd ~
rm -rf JobOs
git clone https://github.com/rosnnn/JobOs.git
cd JobOs
cp .env.example .env
# Edit .env with your real runtime keys and credentials

docker compose up -d --build
```

Then initialize data if needed:

```bash
docker compose exec api python scripts/init_db.py
```

## Security Notes

- Do not commit .env.
- Do not commit runtime credential stores.
- Store production credentials only on the server .env.

## Docs

- Architecture: docs/ARCHITECTURE.md
- Roadmap: docs/ROADMAP.md
- Agent protocol: docs/AGENT_PROTOCOL.md
