# Engineering decisions

## 2026-09-23 — Local-first practice and visible algorithm work

The default experience should open with a usable, no-session algorithm trace,
so the product reads as an interactive learning studio rather than a quiz
entry form. Practice sessions open directly at the lesson; measured study
sessions retain the baseline for evaluation comparability. The everyday setup
uses the existing local API, SQLite database, and local MediaPipe assets.
Docker/PostgreSQL remains an optional acceptance
path, not a requirement for using the application. Google Fonts was removed so
the interface does not make a runtime request to an external font host.

## 2026-09-23 — Order support lifecycle writes

The modal waits for the support-view write to finish before enabling accept or
follow-up actions. The API treats `viewed` as a transition from `offered`; a
late view cannot overwrite `accepted`. This closes a reproduced live-browser
race and has regression coverage.

## 2026-09-22 — Rebuild instead of polishing the landing screen

The initial implementation had a polished first screen but did not support the data integrity, study, and recovery claims in the presentation. The rebuild prioritizes truthful evidence and complete learner journeys over decorative polish.

## 2026-09-22 — Keep the original presentation

`final.pptx` is preserved as the source artifact. A revised deck will be created only after the application has real screenshots and verified findings; no unsupported results will be copied into it.

## 2026-09-22 — Camera signals are context

Face presence and head orientation are observable signals. They do not establish confusion, boredom, attention, or comprehension. Camera loss must never become a positive measurement.

## 2026-09-23 — Basic behavioral indicators stay descriptive

Blink events use eye-aspect ratios; approximate gaze direction uses iris
position; yaw, pitch, and roll use MediaPipe's facial transformation matrix
relative to a neutral calibration. Only cumulative blink count and compact
gaze/pose summaries may enter consented session events. Frames and landmarks
remain local, unavailable and multiple-face measurements stay null, and none
of these indicators can select an intervention.

## 2026-09-22 — Persistence and research boundaries

The Compose acceptance path selects PostgreSQL through SQLAlchemy and keeps
the local SQLite file only as a documented convenience. Fresh schema and
indexes are versioned in `backend/migrations/`. Participant session tokens
can read only their own records; session listing, reset boundaries, and study
exports require a separate researcher credential.

## 2026-09-22 — Local camera assets

`npm run fetch:vision` writes pinned MediaPipe WASM and Face Landmarker assets
under `public/models`. If setup has not supplied those files, the UI reports an
unavailable camera signal and continues the lesson rather than inventing a
detection.

## 2026-09-22 — Canonical retries and progress heartbeats

Assessment and follow-up endpoints return the first saved result for repeated
question keys instead of allowing a retry to overwrite grading or helpfulness.
Terminal support states cannot be reopened by late view requests. The browser
also sends a five-second progress heartbeat so section and timing state survives
reloads during reading.

## 2026-09-23 — Server-measured friction trigger

Checkpoint submissions now return the server-measured presentation-to-submit
interval. The browser forwards that value and the current section revisit
count to the decision endpoint after every incorrect checkpoint, so the
configured long-response/revisit rule is reachable without requiring a
two-error streak. Pilot thresholds are environment-configurable and recorded
with the policy version.

## 2026-09-23 — Derived personalization aggregates

Completed personalized support outcomes are materialized in
`personalization_aggregates` by participant, reset boundary, concept, and
support type. Startup backfills the table from completed follow-ups so legacy
history remains usable, and completion updates it immediately. Incomplete,
dismissed, and skipped support never enters the aggregate.

## 2026-09-23 — Separate feedback from learning outcomes

The results surface records support helpfulness separately from follow-up
correctness, along with optional usability, ease-of-use, and free-text comments.
These fields are attached to the session and exported for descriptive pilot
feedback; they do not affect intervention selection or learning scores.


## 2026-09-23 — Missing and ambiguous camera measurements

Camera-off, model-failure, and frame-failure states use unavailable (`null`)
measurements. The worker requests up to two faces so a multiple-face frame is
stored as ambiguous context rather than being treated as a valid single-learner
measurement. Neither condition selects remedial teaching.


## 2026-09-23 — Persisted section visits

Section navigation counts are stored as a version-neutral JSON map on the
session alongside the current section and timing fields. Heartbeats and
explicit navigation progress updates write the map, allowing revisit-based
difficulty evidence to survive reloads without creating a separate high-volume
visit table.


## 2026-09-23 — Executable lesson traces

The visualizer uses explicit per-algorithm state rather than advancing a
cosmetic index. Binary search updates low/high bounds, linear search advances
its inspected index, and bubble sort advances pass and neighbor cursors. Learners
can edit comma-separated sample values and reset the trace; messages describe the
actual comparison or boundary update.


## 2026-09-23 — Worker WASM module loading

The Face Landmarker worker passes `useModule=true` to
`FilesetResolver.forVisionTasks`. This matches the locally served ES-module WASM
assets and was verified by a browser worker initialization returning `ready`; it
avoids the `ModuleFactory not set` failure seen with the default loader.


## 2026-09-23 — Repeat support question banks

Each lesson now carries two concept-specific follow-up banks. The first support
event for a participant and reset boundary uses `follow_up`; later support for
the same concept uses `follow_up_repeat`. The selected bank is persisted on the
intervention so retries, reloads, exports, and server grading all refer to the
same equivalent question set.


## 2026-09-23 — Explicit model-failure state

Worker initialization failures carry a `phase=model` marker and render a
model-unavailable status while retaining normal interaction evidence. Frame
processing failures use a separate status. Neither path creates a positive
face measurement or a learning-support trigger.


## 2026-09-23 — Isolated PostgreSQL acceptance check

PostgreSQL verification runs through an isolated Compose project and removes
host port bindings, so it can coexist with the local SQLite/API demonstration.
The script creates a session, restarts both database and API services, reloads
the session, and records a machine-readable result. A missing Docker engine is
recorded as an external block rather than reported as a passing check.


## 2026-09-23 — Retention sessions are separate records

The optional 48–72 hour check is created as a new session with
`study_kind=retention`, starts directly in the retention phase, and uses the
same server-side answer grading and progress persistence as ordinary sessions.
This keeps retention answers separate from primary pre/post scores and makes
the follow-up restartable without reopening a completed study session.
