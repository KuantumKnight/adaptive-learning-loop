# Pilot evaluation protocol

This protocol is for a three-volunteer academic feasibility pilot. Report technical behavior, usability, and descriptive score changes. Do not present the results as proof that personalization causes better learning.

## Before collecting data

1. Obtain the approval or classroom guidance required by your institution.
2. Explain that the camera is optional and that, with consent, the prototype stores blink counts and approximate gaze/head-pose summaries with learning events, not raw video or landmarks.
3. Use a participant code such as `P01`; do not enter names in the app.
4. Freeze the commit, rule thresholds, lesson content, and question sets. Record the commit hash and browser used.
5. Run `npm run test:behavior`, `pytest backend/tests -q`, and `npm run build`.

## Session procedure

1. Give every participant the same camera-free controls tutorial. Before their personalized measured session, complete one support interaction in a separate practice session on that lesson. Record this extra exposure as a limitation.
2. Follow the fixed rotation below. Each participant completes one lesson in each mode, and the nine lesson/mode pairings each occur once.
3. Ask the participant to complete the pre-test, lesson, checkpoints, and post-test without coaching on answers.
4. Keep the camera disabled in all measured sessions. Validate camera behavior separately with explicit consent and record its availability.
5. At the end, record the participant’s 1–5 helpfulness rating for any accepted support and collect one open-ended comment.
6. If feasible, run a separate retention session 48–72 hours later. Exclude it from primary-session charts.
7. Download the session CSV from the results screen and store it with the participant code.

## Required measures

- Pre-test and post-test correctness.
- Checkpoint correctness and follow-up correctness after support.
- Completion time.
- Number of automatic prompts and accepted interventions.
- Intervention kind and trigger reason.
- Camera availability and missing-signal periods.
- Helpfulness rating and open-ended feedback.

## Analysis

Use descriptive summaries only: per-mode counts, score changes, median completion time, intervention acceptance rate, and follow-up correctness. Show individual session traces alongside the aggregate table so the small sample size is visible. Exclude incomplete follow-ups from intervention-effectiveness updates and label missing observations in the report.

Suggested report wording: “In this small pilot, the prototype completed the intended sensing-to-intervention loop and recorded preliminary descriptive patterns. The sample is too small to support a causal claim about learning improvement.”

## Facilitator run sheet

Complete one row per participant before opening the app. Keep this sheet with
the exported session files, but store the code-to-person key separately from
the research dataset.

| Field | Entry |
|---|---|
| Participant code | `P__` |
| Practice session ID |  |
| Measured session IDs | Static: __ / Rule-based: __ / Personalized: __ |
| Lesson-to-mode assignment | See rotation table below |
| Session order | 1 / 2 / 3 |
| Browser and OS |  |
| App content/policy version | Read from session export |
| Camera condition | denied / disabled / consented and available / unavailable |
| Prior personalized history | none / practice only / documented session IDs |
| Retention due date | 48–72 hours after measured session |
| Retention session ID |  |
| Completeness notes |  |

Use the following three-row rotation. `L`, `B`, and `S` mean
linear search, binary search, and bubble sort. Each participant completes all
three modes once; the table rotates both lesson and mode order.

| Participant | Session 1 | Session 2 | Session 3 |
|---|---|---|---|
| P01 | Static–L | Rule-based–B | Personalized–S |
| P02 | Rule-based–S | Personalized–L | Static–B |
| P03 | Personalized–B | Static–S | Rule-based–L |

## Consent and facilitator wording

Read this before any measured session and follow institutional requirements:

> You are being invited to try a short learning prototype. Participation is
> voluntary and you may stop at any time. The prototype records answers,
> response times, navigation events, and the intervention support shown. The
> webcam is optional. If you consent to it, processing happens in your browser
> and only summarized face presence, blink counts, approximate gaze direction,
> and approximate head pose are sent; raw video and facial landmarks are not
> stored. These signals are
> observable context, not proof of attention, confusion, or comprehension.
> Your participant code is used in the research export instead of your name.
> Ask the facilitator how the data will be stored, who can access it, and how
> to withdraw under the applicable institutional process.

Facilitator instructions: do not coach answers, do not describe a camera
signal as a mental state, record interruptions and missing data, and label any
practice or synthetic session so it cannot enter the measured summary.

## Short feedback form

Ask immediately after each measured session:

1. How clear were the lesson explanations? (1–5)
2. How easy was it to know what to do next? (1–5)
3. If support appeared, how useful was it? (1–5, or “not shown”)
4. Did any support interrupt your place in the lesson? (yes / no)
5. What was confusing or frustrating?
6. What would you change before using this again?

## Data dictionary

| Field | Meaning | Allowed interpretation |
|---|---|---|
| `participant_code` | Research code, not a name | Grouping key within the study |
| `session_id` | Unique session identifier | Joins records from one run |
| `mode` | `static`, `rule_based`, or `personalized` | Describes configured behavior |
| `study_kind` | `practice`, `study`, or `retention` | Retention is a separate optional follow-up session; exclude it from the primary pre/post comparison |
| `data_origin` | `observed`, `synthetic_demo`, or `legacy_unverified` | Provenance flag; never omit it |
| `content_version` / `policy_version` | Versions recorded at session creation | Required for reproducibility |
| `phase` | `pre`, `checkpoint`, `post`, or `follow_up` | Assessment location |
| `correct` | Server-graded answer result | Descriptive correctness only |
| `response_time_ms` | Presentation-to-submission interval | Timing proxy; inspect missing values |
| `active_time_ms` / `elapsed_time_ms` | Progress heartbeat durations | Active excludes hidden-tab seconds when recorded |
| `intervention_status` | Lifecycle state | Offered, viewed, accepted, dismissed, skipped, completed |
| `follow_up_correct` | Correctness after support | Outcome proxy; partial follow-ups are excluded from effectiveness |
| `helpfulness` | Optional 1–5 learner rating | Separate from correctness |
| camera summary fields | Face presence, cumulative blink count, approximate gaze direction, and head-pose angles | Observable context only; null means unavailable and angles are relative to the neutral calibration |
