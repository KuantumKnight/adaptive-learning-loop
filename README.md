# Loop / Adaptive Learning

An academic prototype of a closed learning loop, available at [adaptive-learning-loop.vercel.app](https://adaptive-learning-loop.vercel.app):

**observe → estimate difficulty → offer help → measure the response → personalize future help**

The project includes three short algorithm lessons (linear search, binary search, and bubble sort), three comparison modes, explainable intervention rules, learner-specific intervention history, CSV export, and a camera-optional learner signal panel. With camera consent, summarized blink counts, approximate gaze direction, and head-pose angles are recorded; raw camera frames and landmarks stay in the browser.

## What makes it different from a quiz

The algorithm trace is an executable model: learners can edit a sample, step
through comparisons, and see the actual search bounds or sort swaps change. In
adaptive modes, checkpoint answers or a help request can offer support; the
learner chooses whether to use it, then answers two new checks. Only completed
checks affect that participant's later support choice. The app records this
small learning loop and explains why support was offered. It does not claim to
detect feelings or prove that a support caused learning. Static, rule-based,
and personalized modes let the team compare the same lessons with different
support policies.

## Run locally (SQLite, no Docker)

The everyday development path is fully local: Vite, FastAPI, the SQLite file
under `data/`, and the checked-in MediaPipe model/WASM assets run on this
machine. Docker is not needed for normal app use. The browser sends API traffic
to `localhost`; camera frames and landmarks stay in the browser. If packages
and model assets are already installed, runtime use does not need an external
service.

### Backend

```powershell
python -m venv .venv
.\\.venv\\Scripts\\Activate.ps1
pip install -r backend/requirements.txt
python backend/prepare.py
uvicorn backend.app.main:app --reload --port 8000
```

### Frontend

In a second terminal:

```powershell
npm ci
npm run dev
```

Open http://localhost:5173. If the API is hosted elsewhere, set `VITE_API_URL` before starting Vite.

Pinned MediaPipe WASM and model assets are checked in under `public/models`. Run
`npm run fetch:vision` only when intentionally updating those assets. The camera
requires consent and a compatible browser; the lessons work without it.

Public entry creates an isolated `demo` participant and labels its records
`synthetic_demo`. Measured study, research practice, retention, researcher
exports, and participant resets require `IDP_RESEARCHER_TOKEN`. Production
has no default researcher credential. Configure it as a sensitive environment
variable and share it only with the facilitator.

## Hosted deployment

`vercel.json` defines Vite and FastAPI as Vercel Services, with same-origin
`/api` and `/health` routes. Production and preview each use a distinct Neon
PostgreSQL database on the free plan. To provision a new environment, configure
`DATABASE_URL` and `IDP_RESEARCHER_TOKEN`, then run the **explicit** release
command `python backend/prepare.py` against that database before deploying.
The web instance does not migrate, reseed, or rebuild aggregates at startup.
The local SQLite database in `data/` is separate and is never deployed.

Run the nine lesson/mode browser journeys, a reload during a question and a
partial follow-up, and the PostgreSQL checks on a preview deployment before
promoting a study build. See [evaluation protocol](EVALUATION.md) and
[technical verification](docs/verification.md). Volunteer outcomes and
real-camera checks are pending human participation and cannot be replaced by
synthetic demonstrations.

### Optional: Docker Compose (PostgreSQL acceptance path)

```powershell
docker compose up --build
```

Use this only when you need to verify the separate PostgreSQL acceptance path.
Compose starts PostgreSQL 16, runs the FastAPI service through SQLAlchemy, and
keeps the database in the `postgres_data` volume. Docker Desktop must be
running. The ordinary local app continues to use SQLite at
`data/idp.sqlite3`; set `IDP_DB_PATH` to change that location.

To run the clean PostgreSQL acceptance check without disturbing a local API,
use:

```powershell
.\scripts\verify-postgres.ps1
```

The script uses an isolated Compose project, verifies health and migrations,
creates a session, restarts PostgreSQL and FastAPI, confirms the session still
loads, and writes `artifacts/postgres-verification.json`. It exits with status
2 and records `blocked_external` when Docker Desktop is unavailable.

The researcher endpoints (`/api/research/sessions`, `/api/research/assignments`,
reset, and CSV export) require `X-Researcher-Token`; Compose uses the local
default `local-researcher`. Set a unique `IDP_RESEARCHER_TOKEN` before any shared or
study deployment. Session endpoints require the per-session `X-Session-Token`
returned at creation.

Pilot thresholds are versioned with the policy and can be changed through
`IDP_LOOK_AWAY_SECONDS` (default `30`), `IDP_RESPONSE_TIME_MS` (default
`45000`), and `IDP_INTERVENTION_COOLDOWN_SECONDS` (default `90`). Record the
values used with the software version before measured sessions.

## How the loop works

- `static` never creates automatic interventions.
- `rule_based` responds to explicit help requests, two consecutive checkpoint errors, and error-plus-friction evidence.
- `personalized` tries unused support types, then selects the type with the best smoothed follow-up score: `(outcome + 1) / (completed + 2)`.
- Follow-up checks update intervention effectiveness only when completed.
- Automatic prompts have a 90-second cooldown. Learner-requested help remains available.
- Camera signals are optional and are interpreted as observable context, not proof of comprehension.

## Verification

```powershell
pytest backend/tests -q
npm run build
```

The backend test suite checks lesson seeding, event idempotency, the closed-loop intervention path, and the static-mode safety rule.

## Evaluation export

At the results screen choose **Download CSV**. Researchers can list sessions with `GET /api/research/sessions` and download the reconciled study export from `GET /api/research/export.csv` using the researcher header. The export includes answer records, interventions, follow-up outcomes, versions, mode, study/practice designation, completeness metadata, and sanitized signal summaries including explicit multiple-face ambiguity. Missing signals remain blank/unavailable. Use participant codes instead of names and obtain consent before collecting volunteer data.

After measured sessions, generate descriptive artifacts from the exported CSV:

```powershell
python scripts/generate-study-charts.py study-export.csv --output-dir artifacts/study
```

The generator includes only `data_origin=observed` and `study_kind=study` rows and refuses to create charts when no eligible observations exist. Retention sessions are exported separately and are not folded into the primary pre/post comparison.

See [EVALUATION.md](EVALUATION.md) for the fixed pilot procedure, measures, and reporting language for a 3–6-person study.

For a repeatable technical walkthrough, use [docs/demo-script.md](docs/demo-script.md). The report structure and explicit pending-evidence language are in [docs/report-template.md](docs/report-template.md).

The current evidence-based technical report is [artifacts/report/adaptive-learning-report.md](artifacts/report/adaptive-learning-report.md). It does not contain fabricated volunteer findings.

If a rehearsal needs a visible history before participant sessions exist, run
`python scripts/generate-synthetic-demo.py`. It writes an explicitly labelled
artifact under `artifacts/synthetic-demo/`; the chart generator intentionally
rejects that file.
