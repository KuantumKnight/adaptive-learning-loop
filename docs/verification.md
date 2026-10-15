# Verification record

## 2026-09-23 — Local-first start and algorithm preview

- Opened the clean local app at `http://127.0.0.1:5173/` in the in-app browser.
- Confirmed the lesson selector, editable sample input, target, `Use input`, and
  `Step` controls are exposed to the accessibility tree before any session is
  started.
- Stepped the default binary-search sample. The interface reported
  `low 0, middle 3, high 6: 10 is larger, move low to 4` and highlighted the
  compared value.
- Verified the app presents its actual loop: interaction, answer evidence,
  offered support, and two follow-up checks. Copy explicitly says the camera
  does not infer feelings.
- Practice sessions begin directly at instruction; measured study sessions
  preserve the baseline. An API test checks both persisted start phases. The
  production build passed after changes.
- Opened a local practice session (`local-ui-walkthrough`) and confirmed it
  landed on the explanation, worked example, and live trace instead of a quiz.
  Reload restored the same lesson. Later sessions tried unused supports, saved
  two follow-ups per support, and selected simplified support again after it
  had the strongest completed outcome. A repeated view/accept race found in
  this journey has been fixed and covered by a regression test.
- These five agent-run practice sessions are explicitly marked
  `data_origin=synthetic_demo` in the local database. Four same-learner sessions
  exercised support history; a separate learner received the default support
  and had no personalization aggregates, confirming learner isolation. These
  are software verification only, not participant observations or study results.
- Removed the Google Fonts runtime import; no other third-party runtime assets
  were added. PostgreSQL/Docker remains optional for the local SQLite workflow.

## Environment

- Workspace: `E:\Career_Development\Projects\idp`
- Frontend: React, TypeScript, Vite
- Backend: FastAPI
- Local convenience persistence: SQLite; Compose config selects PostgreSQL through SQLAlchemy and versioned SQL migrations.
- Source presentation: `final.pptx`

## Checks to run after each milestone

```powershell
pytest backend/tests -q
npm run build
```

The current local run reports 24 backend tests passing and a successful Vite
production build. The tests cover server grading, hidden answer keys, mode
isolation, event idempotency, consecutive-error reset, and completed-history
personalization, intervention lifecycle idempotency, provenance-safe exports,
the full nine lesson/mode combinations, raw-camera rejection, health endpoints,
canonical retry behavior for answers and follow-ups, terminal intervention
state protection, automatic cooldown versus explicit help, and neutral camera
context handling, progress membership validation, completed-session mutation
rejection, and server-derived response timing. They do not
replace browser or human-study evidence.

The final verification must additionally run against a clean PostgreSQL database and exercise the browser journeys in the completion plan. A successful HTTP 200 response alone is not browser verification.

## Current blockers

- `docker compose up -d db` could not start because the local Docker Desktop Linux engine is not running. PostgreSQL acceptance evidence is therefore pending an environment with a running Docker daemon.
- `scripts/verify-postgres.ps1` was added as the repeatable acceptance check. Its current artifact at `artifacts/postgres-verification.json` records `blocked_external` because the Docker engine is unavailable; it does not claim PostgreSQL persistence was verified.
- The native browser connector is unavailable in this environment, so the real localhost verification uses the `agent-browser` fallback. The all-lessons/all-modes matrix is complete; remaining external evidence is real model-load/camera behavior and a formal assistive-technology review.

## Evidence policy

- Synthetic fixtures are allowed only in tests and explicitly labelled demo data.
- No human-study result may be shown until it comes from a consented participant export.
- Missing camera signals must be recorded as unavailable.
- Every UI metric must reconcile with persisted records and an export.

## Direct browser evidence (2026-09-22)

With FastAPI on `127.0.0.1:8000` and Vite on `127.0.0.1:5173`, the actual
learner UI was exercised in the Codex in-app browser:

- Opened a personalized binary-search session and completed the baseline.
- Used the visualizer step control and revisited lesson sections.
- Submitted two incorrect checkpoint answers; the UI offered a simplified
  intervention with the reason “Two checkpoint answers were incorrect in a
  row” and the selection reason “exploration of an unused support type”.
- Accepted the support, completed both distinct follow-up checks, and saw the
  support close without changing the learner’s checkpoint position.
- Reloaded during the checkpoint; the same session and question were restored
  from server progress.
- Started another session for the same participant; explicit help selected a
  worked example and displayed the saved-history selection reason.
- Opened the researcher workspace and confirmed its credential-gated empty
  state. Camera-off status was shown as “Camera off”; no browser permission was
  granted during this check.
- Stopped the API while a session was open; the header changed to “2 pending”
  and the page displayed the local retry notice. After restarting the API, the
  queue flushed and the header returned to “saved”.
- Visual inspection caught a dark-on-dark answer-choice regression inherited
  from the first pass. The option controls now use the light panel palette;
  the live screenshot was rechecked after hot reload and is readable.
- Browser smoke coverage also opened static Bubble Sort, rule-based Linear
  Search, and personalized Binary Search sessions. The backend matrix test
  covers all nine lesson/mode combinations; completing every full lesson in
  the browser remains a final study/demo pass.
- Entered the documented local researcher credential in the workspace. The UI
  displayed session rows with mode, purpose, answer/support counts, and
  `legacy_unverified` provenance, and the study CSV control was enabled.
- Opened a support dialog from the learner UI; the accessibility tree exposed
  it as a labelled modal, focus moved to the dialog, and pressing Escape
  dismissed it and returned to the lesson.
- Camera code now keeps unavailable head-orientation and blink values as
  `null`, exposes an explicit calibration control, and computes exploratory
  blink counts inside the worker from MediaPipe blendshapes. Real camera
  permission, calibration, and hardware plausibility evidence remains pending
  because no consenting webcam session was run. The pinned model and WASM assets were fetched with
  `npm run fetch:vision` and both local asset URLs returned HTTP 200. A direct
  browser worker initialization using those local URLs returned `ready` after
  enabling ES-module WASM loading. A blank synthetic canvas frame then returned
  `{present:false, ambiguous:false, lookingAway:null}` from the worker without
  sending the image to the API. The
  source URL and MediaPipe Apache-2.0 notice are recorded in
  `public/models/README.md`.
- The learner now sends a five-second progress heartbeat using the current
  phase, question, section, section-visit map, and active/elapsed timers, so
  reading progress and revisits are persisted even before the next explicit
  navigation action. A live API check saved `{explain: 2, example: 1}` and
  recovered the same map through both detail and resume. The browser then
  revisited two lesson sections, reloaded, and recovered `{explain: 2,
  simplify: 1}` from the real session state.
- Incorrect checkpoint submissions now send the server-measured response
  interval and section revisit count to the decision policy. The regression
  suite verifies that a single incorrect answer with a response above the
  configured pilot threshold can trigger support without a two-error streak.
- Personalized completion writes a participant/reset-boundary/concept/support
  aggregate after the second follow-up. Startup backfills that derived table
  from completed records, and the personalization test checks the stored
  completed count and outcome sum.
- Outbox entries now retain the session token captured when the event was
  queued, preventing a later session from retrying an old event with the wrong
  authorization context.
- Outbox retries now persist attempt counts and use bounded exponential
  backoff (up to 30 seconds) instead of hammering a failed API every five
  seconds.
- The results surface now derives lifecycle counts, follow-up correctness,
  helpfulness, active/elapsed duration, camera coverage, provenance, and a
  latest-actions timeline from the saved session detail response. Missing
  signal coverage and ratings render as `Unavailable`.
- Session and researcher CSV exports now include active/elapsed timing, camera
  consent, sanitized signal-summary rows, and fixed-width row validation; the
  export regression test checks every row reconciles with its header.
- The results surface now collects optional support-helpfulness, usability,
  ease-of-use, and free-text feedback. A live practice session saved all four
  fields, session detail returned them, and both session and researcher CSV
  exports preserved fixed-width rows with the feedback columns. Feedback is
  descriptive usability evidence and is not mixed into intervention correctness
  aggregates.
- The lesson progress indicator exposes an accessible progressbar with
  numeric values, and the webcam preview has an explicit accessible label.
  The live browser pass also checked the narrow 390×844 layout and dialog
  focus/Escape behavior. An axe 4.12.1 audit reports zero WCAG violations on
  the live lesson page; its two incomplete checks are the expected gradient
  contrast heuristic and the visual-only webcam preview. A full screen-reader
  review remains external.
- Frontend dependency declarations are pinned to the lockfile-resolved
  versions; `npm install --package-lock-only --ignore-scripts` reports the tree
  up to date.
- `npm ci --dry-run --ignore-scripts --no-audit --no-fund` resolves the pinned
  tree successfully.
- `docker compose config --quiet` validates the Compose file syntax locally;
  starting the PostgreSQL service remains blocked because Docker Desktop's
  Linux engine is unavailable in this environment.
- A fresh SQLite initialization check created all three lessons and the
  `section_visits` column from an empty database; this validates the additive
  startup path while PostgreSQL execution remains externally blocked.
- The FastAPI lifespan migration leaves the 24-test run free of framework
  deprecation warnings.
- The one-active-support regression now covers two distinct support requests for the same session; both return the same intervention ID and the persisted intervention count remains one. A partial unique index protects concurrent PostgreSQL/SQLite inserts.
- The browser outbox now removes permanent 4xx responses for completed,
  expired, or invalid sessions while retaining exponential backoff for network
  failures. A live session with a stale completed-session queue drained it to
  zero after the API was available; the same session then accepted a normal
  answer and static mode offered no automatic support.
- `scripts/generate-study-charts.py` was exercised with one observed measured
  fixture and produced SVG, JSON, and session-summary outputs. An empty export
  exits nonzero with an explicit refusal, so no fabricated chart is produced.
- `scripts/generate-synthetic-demo.py` generated
  `artifacts/synthetic-demo/synthetic-session-export.csv` with
  `data_origin=synthetic_demo` and a manifest declaring no human participant.
  Passing that file to the study-chart generator exits nonzero with the
  expected refusal, keeping rehearsal data out of study summaries.
- `artifacts/report/adaptive-learning-report.md` was added as the current
  technical report. It cites only the verified 24-test/browser evidence and
  explicitly leaves PostgreSQL, webcam plausibility, volunteer findings,
  citation sign-off, and recording as pending handoff items.
- The content migration now provides two concept-specific follow-up checks and
  a second equivalent bank for each lesson. The personalized-history regression
  verifies that a later support event records `follow_up_repeat` and accepts
  both repeat questions through the same server-side grading path.
- Retention sessions are now a first-class session purpose. Creating one starts
  persisted progress in the `retention` phase, accepts only retention-bank
  questions through server grading, and the results surface can launch a new
  retention session for the same participant and lesson. The regression suite
  covers creation, resume state, and grading; the 48–72 hour human follow-up is
  still external.

This evidence is complemented by the full all-lessons/all-modes matrix below,
the outage/retry check, and the narrow-layout pass. It remains separate from
consenting-person webcam validation and human-study evidence.

## Full browser matrix evidence (2026-09-23)

The `agent-browser` CLI exercised the actual Vite/FastAPI application and
completed all nine lesson/mode combinations using the visible question controls:

| Lesson | Static | Rule-based | Personalized |
|---|---|---|---|
| Linear Search | completed | completed | completed, including a two-error simplified-support flow and two follow-ups |
| Binary Search | completed | completed | completed |
| Bubble Sort | completed | completed | completed |

Each run reached the session results surface. Screenshots captured during the
pass are stored under `artifacts/screenshots/` (`setup.png`,
`personalized-bubble-results-full.png`, `research-loaded.png`,
`latest-lesson.png`, and the locked research state). The browser matrix did
not prove real hardware/model
plausibility.

In a consented browser session without an available camera device, clicking
`Enable camera` produced `Camera unavailable · interaction signals still work`.
The live debug panel showed face presence, head orientation, multiple-face
ambiguity, and exploratory blink values as `unavailable`, with no support
intervention triggered. Camera-off starts now also use `null` for every
measurement until a valid local summary arrives. This proves the failure path;
it does not validate real landmark quality or a real multiple-face capture.

The researcher workspace now loads the versioned pilot rotation from
`GET /api/research/assignments` behind the researcher credential. The live
browser displayed P01 through P06 after loading the workspace, while the API
test confirms unauthorized access is rejected and the returned content/policy
versions match `v2`.

The live lesson endpoint reports, for each of the three lessons, 3 pre-test,
6 checkpoint, 3 post-test, 2 initial follow-up, 2 repeat follow-up, and 3
retention questions, plus a visualizer. Public question objects contain no
`answer` property.

The browser also opened a real `retention` session through the running Vite and
FastAPI services. It restored the retention phase, displayed all three
retention questions, graded the three submitted answers, and reached the saved
results surface with a retention-only timeline.

The browser worker was also initialized with a deliberately missing model asset.
It returned `{phase: "model"}` with the MediaPipe load error, proving that the
frontend can distinguish model initialization failure from an ordinary frame
signal failure without converting the missing signal into a face detection.

The live start page was keyboard-traversed with Tab. Focus reached the
participant input, lesson selector, mode controls, and camera-consent input in
document order; the page exposed semantic names for each control. Screen-reader
and 200% zoom review remain manual follow-up checks.

At 320×844 with reduced motion enabled, the live start screen was captured at
the top and scrolled form positions. The layout remained single-column with no
horizontal clipping; all mode controls, camera consent, and primary actions
were readable. The browser was restored to 1280×900 after the check.

A 640px-wide live viewport proxy for 200% browser zoom reported equal document
and viewport widths (`scrollWidth == innerWidth`) and showed the responsive
single-column form without horizontal overflow. The browser was restored to
1280×900 afterward; exact OS screen-reader review remains manual.

The preserved local database currently reports both `legacy_unverified` and
`observed` provenance values; legacy rows were not deleted or silently treated
as new measurements.

The presentation literature audit is recorded in `docs/literature-audit.md`.
It inventories all 20 entries, links primary records where identified, and
marks generic or unresolved rows as unusable until a team member supplies and
checks the exact source.

## Revised presentation evidence (2026-09-23)

`artifacts/revised-deck/adaptive-learning-rebuild.pptx` was generated from the
verified technical evidence and finalized with the presentation artifact
validator. The 8-slide deck passed package integrity, layout geometry, font,
and import checks; all eight rendered slides were visually inspected in
`artifacts/revised-deck/rendered/`. The deck uses real application screenshots
and labels practice/demo records and human-study work separately. It does not
claim volunteer findings, PostgreSQL completion, or real webcam plausibility.
