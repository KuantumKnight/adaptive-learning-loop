# Adaptive Learning Loop — project report draft

## Abstract

This project implements a closed learning loop for three algorithm lessons:
the system observes interaction evidence, estimates a difficulty state with
explainable rules, offers a support intervention, measures two follow-up
answers, and uses completed outcomes to choose later support. The prototype is
designed for technical validation and a small preliminary usability pilot. It
does not claim that webcam signals reveal mental states or that personalization
causes learning gains.

## Architecture

The learner interface is a React and TypeScript Vite application. FastAPI
stores sessions, answers, events, interventions, follow-ups, provenance, and
version metadata. PostgreSQL is the Compose acceptance database through
SQLAlchemy; SQLite is retained for local convenience. Face Landmarker runs in a
browser worker. Only five-second summaries are eligible for API submission;
raw frames and landmarks remain local.

## Method

Each lesson contains separate pre-test, checkpoint, post-test, follow-up, and
retention question banks. Server-side grading uses answer keys that are never
sent in public lesson responses. Difficulty support is triggered by an explicit
help request, two consecutive checkpoint errors, or an error combined with
revisits or a configurable response-time threshold. Webcam absence or looking
away is recorded as observational context and can prompt “Continue or pause?”
only. Automatic support has a 90-second cooldown and one active intervention.

Personalized selection queries completed two-answer outcomes for the same
participant and reset boundary. Unseen support types are explored in fixed
order; after exploration, the selected type maximizes the smoothed score
`(sum correct + 1) / (completed outcomes + 2)`. Dismissed, skipped, and partial
follow-ups do not update effectiveness.

## Implemented technical evidence

The current automated suite contains 24 backend tests. It covers server
grading, hidden answer keys, all nine lesson/mode combinations, event
idempotency, streak reset, intervention lifecycle, cross-session
personalization, provenance-safe exports, raw-camera rejection, health
endpoints, canonical assessment/follow-up retries, terminal-state protection,
cooldown behavior, neutral camera-context handling, progress membership validation, completed-session mutation rejection, and server-derived response timing. A live browser path has also demonstrated a two-error trigger,
support acceptance, two follow-ups, repeat support questions, retention-session
grading, model-load failure handling, reload recovery, later personalized
selection, and offline event retry.

## Human evaluation status

Human-study findings are pending. The required study uses consenting adults,
participant codes, rotated lesson-to-mode assignments, separate practice and
measured sessions, and optional 48–72-hour retention checks. Until those
sessions exist, this report must not contain aggregate human score changes,
claims of improved learning, or claims of adaptation accuracy.

## Limitations

The pilot size is too small for causal inference. Follow-up correctness is an
outcome proxy. Webcam summaries describe face presence, blink counts,
approximate gaze direction, and calibration-relative head pose; they do not
measure attention or emotion. Timing thresholds are pilot configuration values, not
validated scientific constants. Missing camera, incomplete follow-ups, legacy
records, and synthetic demonstrations must remain visibly labeled.

## Reproducibility checklist

- [ ] Start a clean PostgreSQL database with Docker Compose using `scripts/verify-postgres.ps1`.
- [x] Run the backend test suite and frontend production build.
- [x] Verify the public lesson payload has no answer keys.
- [x] Verify session and policy versions are exported.
- [x] Verify active/elapsed timing, persisted section visits, camera consent, and sanitized signal-summary rows are exported.
- [x] Complete the browser matrix for all lessons and modes.
- [ ] Run consenting participant sessions and archive exports.
- [ ] Replace pending study sections with observed values only.
- [x] Add verified technical screenshots and pending-evidence language to a revised deck.
- [ ] Replace the pending sections with measured study findings after the volunteer sessions and final citation sign-off.
