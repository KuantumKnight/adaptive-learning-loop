# Adaptive Learning Loop

## Technical project report

**Evidence cut-off:** 2026-09-23  
**Software version:** content `v2`, policy `v2`  
**Study status:** technical validation complete; human-study findings pending

## Abstract

This project implements a closed adaptive-learning loop for three algorithm
lessons: linear search, binary search, and bubble sort. The application records
learning interactions, estimates difficulty with explainable rules, offers a
support intervention, measures two follow-up answers, and uses completed
participant-specific outcomes to select later support. The camera is optional
and remains a local source of observable context. This report documents the
implemented system and its technical evidence; it does not claim that webcam
signals reveal confusion or that personalization causes learning gains.

## Architecture

The learner interface is a React, TypeScript, and Vite application. FastAPI
provides lesson, session, progress, event, assessment, intervention, feedback,
research, and export endpoints. SQLite is the local convenience database;
PostgreSQL is configured through SQLAlchemy and Docker Compose for acceptance
deployment. Versioned migrations include personalization aggregates, feedback,
section visits, one-active-intervention protection, and repeat follow-up banks.

MediaPipe Face Landmarker runs in a browser worker using locally served pinned
WASM and model assets. Raw frames and landmarks remain transient and local.
With camera consent, summarized face presence, cumulative blink counts,
approximate gaze direction, calibration-relative yaw/pitch/roll, ambiguity, and
signal availability can reach the API. These are observable estimates, not
measures of attention or emotion; real-camera plausibility remains unverified.

## Learning content and modes

Each lesson contains three instructional sections, an editable algorithm
visualizer, prerequisites, objectives, complexity notes, boundary cases,
common mistakes, and server-graded assessment banks. The public lesson contract
contains three pre-test questions, six checkpoints, three post-test questions,
two initial follow-up questions, two equivalent repeat follow-up questions, and
three retention questions per lesson. Answer keys are stored only on the
backend.

The static mode provides the same lesson flow without automatic support. The
rule-based mode uses fixed escalation from simplified explanation to worked
example to guided practice. The personalized mode explores unused support types
and then selects the highest completed outcome using:

```text
(sum of completed follow-up correctness + 1) /
(completed interventions + 2)
```

Dismissed, skipped, and incomplete support never updates that score. A repeat
support event uses the persisted equivalent follow-up bank, so retries and
exports refer to the same questions.

## Adaptation and privacy behavior

Support can be triggered by an explicit help request, two consecutive incorrect
checkpoint answers, or an incorrect answer combined with repeated section
visits or a configurable long response. Automatic support has a 90-second
cooldown and the database enforces one active support item per session.

Camera context is kept separate from learning difficulty. Sustained absence or
looking-away context can produce a dismissible “Continue or pause?” observation;
it cannot select remedial teaching. Missing camera signals remain unavailable.
Model-load failures are reported separately from frame failures. Multiple faces
are recorded as ambiguous rather than as a valid single-learner measurement.

The browser outbox retains stable event IDs and session tokens, retries network
failures with bounded backoff, and drops permanent failures for completed or
invalid sessions. Duplicate event, answer, intervention, and follow-up requests
return canonical saved results.

## Technical verification

The current automated suite contains **24 passing backend tests**. It covers:

- server-side grading and hidden answer keys;
- all lesson and comparison-mode combinations;
- timing, progress membership, section revisits, and reload recovery;
- event, answer, follow-up, and intervention idempotency;
- cooldown, streak reset, one-active-support, and neutral camera context;
- cross-session personalization and completed-only outcome aggregation;
- repeat follow-up banks and retention-session creation/grading;
- provenance-safe exports, raw-camera rejection, and researcher access;
- terminal session protection and health endpoints.

The production frontend build passes. The live browser matrix completed all nine
lesson/mode combinations. A browser retention session completed three retention
questions and reached the results surface. A worker initialized the pinned local
model successfully, a blank frame produced no face, and an invalid model asset
returned a typed model-phase failure. The browser outage path showed pending
events and later returned to saved after API recovery. The live accessibility
audit reported zero axe violations; full screen-reader review remains pending.

## Reproducibility

Run the local stack with the commands in `README.md`, then run:

```powershell
pytest backend/tests -q
npm run build
.\scripts\verify-postgres.ps1
```

The PostgreSQL verifier uses an isolated Compose project, creates a session,
restarts PostgreSQL and FastAPI, and confirms that the session survives. Its
current result is `blocked_external` because Docker Desktop’s Linux engine is
not available in the validation environment. The local API and frontend remain
usable through SQLite and Vite.

For a rehearsal without participant data, run:

```powershell
python scripts/generate-synthetic-demo.py
```

The generated artifact is marked `synthetic_demo`, names no human participant,
and is rejected by the study-chart generator. It must not be used as a study
result.

## Human evaluation status

No volunteer findings are reported in this document. The planned pilot uses
three to six consenting adults, participant codes, rotated lesson-to-mode
assignments, separate practice and measured sessions, optional webcam consent,
and an optional retention check 48–72 hours later. The pilot run sheet,
consent wording, feedback questions, data dictionary, and assignment rotation
are in `EVALUATION.md`.

## Limitations and handoff

The small pilot cannot support causal claims about improved learning. Follow-up
correctness is an outcome proxy, not an intervention effect estimate. Timing
thresholds are configurable pilot settings, not validated scientific constants.
Observable webcam context is not a mental-state label. Legacy records retain a
`legacy_unverified` provenance value, and synthetic rehearsal data remains
separate from study exports.

Before final academic submission, a team member must run the PostgreSQL
acceptance script with Docker available, validate camera behavior with suitable
consenting hardware, conduct the volunteer sessions, replace pending report
sections with observed exports, complete the unresolved citation audit, and
record the final demonstration.
