# Implementation status

This is the working evidence ledger for the adaptive learning project. A requirement is marked **verified** only when the implementation and a direct check both exist.

| Area | Status | Evidence / next action |
|---|---|---|
| Three lessons and comparison modes | verified | `agent-browser` completed all nine lesson/mode combinations on 2026-09-23: Linear, Binary, and Bubble in static, rule-based, and personalized modes; each reached the saved results surface. The public lesson contract now exposes 3 pre, 6 checkpoint, 3 post, 2 initial follow-up, 2 repeat follow-up, and 3 retention questions per lesson. |
| Local-first learner entry | verified | The local start page now exposes an editable algorithm trace before session creation; browser verification stepped Binary Search and observed the actual bound update. Practice opens directly at instruction; measured study keeps its baseline. Remote Google Fonts import removed; README documents SQLite/no-Docker as the default. |
| Repeat support question banks | verified | Each lesson stores two concept-specific `follow_up` checks plus two equivalent `follow_up_repeat` checks. The backend records the selected bank on the intervention; the personalization regression submits the repeat bank in a later session and verifies both answers server-side. |
| Server-side answer grading | verified | Public lesson responses omit answer keys; `test_server_grades_answers_and_hides_keys` passes. |
| Session persistence and resume | verified | Token-protected progress and resume endpoints plus local session restore; browser reload restored the same checkpoint question. |
| Truthful interaction timing and revisits | verified | Question start/submission timestamps, active/elapsed progress, and a persisted section-visit map are stored; the backend test and live API check recovered `{explain: 2, example: 1}` through detail and resume. |
| Idempotent event decisions | verified | Duplicate event test returns saved decision without a second intervention. |
| Cross-session personalization | verified | Backend history test passes; completed outcomes are materialized in `personalization_aggregates`; browser follow-up session selected “worked example” after saved simplified support for the same participant. |
| Intervention lifecycle | verified | Browser accepted and completed both follow-ups; browser Escape dismissed support; API test covers view, skip, and duplicate skip. |
| PostgreSQL migrations | implemented but externally blocked | SQLAlchemy adapter, versioned SQL migrations, Compose healthcheck, and pinned drivers added. `scripts/verify-postgres.ps1` is ready to verify clean startup and restart persistence; its current artifact records `blocked_external` because Docker is unavailable. |
| Legacy provenance | verified | Existing v1 sessions are retained and relabeled `legacy_unverified`; the preserved database contains both legacy and observed provenance values, and `data/idp.sqlite3.pre-rebuild-20260923.bak` preserves a verified rollback snapshot. |
| Worker-based MediaPipe | implemented but unverified | `src/faceWorker.ts` runs local inference; behavior-metric unit tests cover eye-aspect blink events, iris gaze classes, and pose decomposition/calibration; backend tests cover consented scalar summaries and exports. Real-camera signal plausibility remains an external check. |
| Camera unavailable semantics | implemented but unverified | Browser failure-path check showed `Camera unavailable · interaction signals still work` and unavailable face/orientation/multiple-face/blink values; poor-lighting and real landmark validation remain. |
| Offline outbox and retry | verified | Live browser outage showed pending events and a retry notice; after API restart the queue flushed and status returned to saved. Permanent 4xx responses from a completed/expired session are now dropped instead of retried forever. |
| Research workspace and exports | verified | Browser credential entry displayed stored session provenance rows and the P01–P06 rotation loaded from the versioned assignments endpoint; API export/assignment tests cover provenance, privacy, and researcher authentication; the UI exposes mode/purpose filters, rotation, and a reset-history boundary control. |
| Pilot protocol | implemented but externally blocked | `EVALUATION.md` now includes rotation, consent wording, facilitator run sheet, feedback form, and data dictionary; consent, participants, and human sessions remain external. |
| Report and demo package | implemented but unverified | `artifacts/report/adaptive-learning-report.md` now records verified technical evidence and explicit human-study handoff; `docs/report-template.md`, `docs/demo-script.md`, and `artifacts/synthetic-demo/` remain the editable report/demo support artifacts. |
| Accessibility | implemented but unverified | Live semantic/focus checks, dialog Escape behavior, axe 4.12.1 audit with zero violations, narrow 390×844 layout, and reduced-motion/focus-visible styles are documented in `docs/accessibility-checklist.md`; a full screen-reader review remains external. |
| Revised presentation and screenshots | implemented but unverified | `artifacts/revised-deck/adaptive-learning-rebuild.pptx` contains verified technical evidence, live screenshots, and an explicit human-study handoff; final team/content review and measured-study update remain. Original `final.pptx` remains preserved. |

## Completion rule

Do not claim completion while any software item above is missing or while external study requirements remain unrecorded as blocked. Update this ledger after each verification pass.

## Next action queue

1. Exercise real local model loading with a consenting webcam; record unavailable, calibration, and signal plausibility evidence without exporting raw frames.
2. Start PostgreSQL through Docker Compose in an environment with Docker Desktop running and verify clean migration plus restart persistence.
3. Run the documented practice and measured sessions with consenting volunteers, then generate charts, complete the report, and revise the presentation from actual exports.

## Numbered delivery matrix

| # | Requirement | Status | Direct evidence / next action |
|---:|---|---|---|
| 1 | Frontend, backend, database, and development setup | implemented but unverified | React/Vite, FastAPI, Compose, Dockerfiles, and SQLite convenience path exist; `docker compose config --quiet` passes, while clean PostgreSQL startup remains blocked by Docker. |
| 2 | Participant codes, lesson selection, session creation, lesson player | verified | Live browser start screen and session path; API tests cover session creation. |
| 3 | Complete binary-search lesson first | verified | Live browser content, editable visualizer, baseline, checkpoints, support, and follow-ups exercised; the binary trace now updates bounds and finds the target consistently. |
| 4 | Pre-tests, checkpoints, post-tests, results | verified | Browser completed the full lesson flow for all nine lesson/mode combinations; results showed separate scores, lifecycle counts, timing, and event timeline. |
| 5 | Record answers, timings, revisits, help, duration | verified | Server derives response time from the presentation timestamp, returns the canonical timing, and persisted section visits survive detail/resume; the reachable long-response trigger is regression-tested. |
| 6 | Linear-search and bubble-sort lessons | verified | Browser completed Linear Search and Bubble Sort in static, rule-based, and personalized modes. |
| 7 | Camera consent, preview, calibration, off control | implemented but unverified | Browser consent and unavailable-device path exercised; calibration, camera-off after active stream, and real hardware validation remain. |
| 8 | Face presence, gaze direction, blink count, head pose | implemented but unverified | Worker computes local EAR blinks, iris-based direction, and relative yaw/pitch/roll; scalar summaries are consent-gated and exported; real hardware plausibility remains. |
| 9 | Five-second summaries and combined evidence | implemented but unverified | Stable five-second summary sampling now reads the latest signal; server-measured friction trigger and rules exist; full timing audit remains. |
| 10 | Debug panel with measurements and reasons | verified | Live “Show signals” panel exposes availability, timing, observations, and reasons. |
| 11 | Scripted state changes and camera-free usability | verified | Backend rule tests, live camera-off path, and direct browser model-failure worker path pass; real camera permission/hardware remains external. |
| 12 | Simplified, worked-example, guided-practice interventions | verified | All three policy kinds and lesson support content exist; simplified and worked example shown live. |
| 13 | Help without replacing learner place | verified | Support modal overlays current question; reload preserved position. |
| 14 | Rule-based escalation | verified | Policy selection and intervention tests cover fixed escalation. |
| 15 | Two follow-up checks after accepted help | verified | Live session completed two distinct follow-ups; server grades them. Each lesson also has a separate equivalent repeat bank, selected and recorded for a later support event. |
| 16 | One active intervention and cooldown | verified | Database partial unique index enforces one offered/viewed/accepted item per session; API returns the canonical active item for repeated support requests, and cooldown-versus-explicit-help tests pass. |
| 17 | Store outcomes by participant/concept/type | verified | Database schema and personalization test cover participant history. |
| 18 | Correctness outcome plus separate helpfulness | verified | Results feedback form accepts support helpfulness separately from follow-up correctness; live `feedback-manual-2` saved all four fields, session detail returned them, and session/research CSV rows reconciled with their headers. |
| 19 | Rule-based cold start | verified | Fixed-order policy and backend mode tests pass. |
| 20 | Explore unused types then smoothed best score | verified | Formula and completed-history test pass; browser showed later worked-example selection. |
| 21 | Exclude incomplete follow-ups | verified | Query requires two completed follow-ups; test uses completed-only history. |
| 22 | Explanation of personalized selection | verified | Selection reason is rendered in support dialog and stored. |
| 23 | Automated checks before volunteers | verified | 24 backend tests and production build pass. |
| 24 | Practice session for personalization history | implemented but externally blocked | Practice/study field and run sheet exist; human practice is pending. |
| 25 | Each volunteer completes all three modes | externally blocked | Requires consenting volunteers. |
| 26 | Rotate lesson-mode assignment and order | implemented but externally blocked | Six-row rotation table exists in `EVALUATION.md`; execution is pending. |
| 27 | Collect scores, time, interventions, feedback | externally blocked | Feedback form and export fields exist; participant data is pending. |
| 28 | Optional 48–72 hour retention check | implemented but externally blocked | Results now launch a separate retention session with server-graded retention questions and resumable `retention` progress; browser verification completed all three retention questions and reached results, while the 48–72 hour human follow-up remains pending. |
| 29 | Freeze rules and record software version | implemented but unverified | Content/policy versions are stored; final study freeze is pending. |
| 30 | Fix evaluation issues and rerun checks | implemented but unverified | Regression fixes have been rerun locally; study-specific fixes await study data. |
| 31 | Descriptive charts and session summaries | implemented but externally blocked | `scripts/generate-study-charts.py` derives SVG charts, JSON summaries, and session summaries from observed measured CSV rows and refuses empty/practice/synthetic input; real volunteer export is still required. |
| 32 | Architecture, methodology, evaluation, limitations report | implemented but unverified | `artifacts/report/adaptive-learning-report.md` contains architecture, method, technical verification, reproducibility, human-study status, and limitations; observed study sections remain pending. |
| 33 | Verify literature references | implemented but unverified | `docs/literature-audit.md` inventories all 20 slide entries, links verified primary records, corrects the Dostálová/Plch year, and marks unresolved generic labels for removal or source recovery. Final team source check remains pending. |
| 34 | Revised presentation with screenshots/findings | implemented but unverified | `artifacts/revised-deck/adaptive-learning-rebuild.pptx` was finalized, rendered, and visually inspected; it uses real app screenshots and technical validation counts while labeling human findings as pending. Update after the volunteer study. |
| 35 | Repeatable demo and backup recording | implemented but externally blocked | `docs/demo-script.md` and `scripts/generate-synthetic-demo.py` provide a repeatable labelled rehearsal; recording is not yet made. |
| 36 | Clean-checkout README reproduction | implemented but unverified | README and Compose files exist; clean PostgreSQL run awaits Docker. |
