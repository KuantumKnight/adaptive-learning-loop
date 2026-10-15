from __future__ import annotations

import csv
import io
import json
import math
import os
import time
import uuid
import hashlib
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .db import DATABASE_URL, connect, init_db
from .schemas import EventPayload, AnswerCreate, EventCreate, FeedbackCreate, FollowUpCreate, InterventionResponse, ProgressUpdate, SessionCreate

@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.getenv("IDP_ENV", "local") != "production" and not os.getenv("VERCEL"):
        init_db()
    yield


app = FastAPI(title="Adaptive Learning Loop API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://127.0.0.1:5193"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

COOLDOWN_SECONDS = int(os.getenv("IDP_INTERVENTION_COOLDOWN_SECONDS", "90"))
LOOK_AWAY_SECONDS = int(os.getenv("IDP_LOOK_AWAY_SECONDS", "30"))
RESPONSE_TIME_MS = int(os.getenv("IDP_RESPONSE_TIME_MS", "45000"))
INTERVENTIONS = ("simplified", "worked_example", "guided_practice")
CONTENT_VERSION = "v2"
POLICY_VERSION = "v2"
PILOT_ASSIGNMENTS = [
    {"participant_code": "P01", "session_1": "Static · Linear", "session_2": "Rule-based · Binary", "session_3": "Personalized · Bubble"},
    {"participant_code": "P02", "session_1": "Rule-based · Bubble", "session_2": "Personalized · Linear", "session_3": "Static · Binary"},
    {"participant_code": "P03", "session_1": "Personalized · Binary", "session_2": "Static · Bubble", "session_3": "Rule-based · Linear"},
]
SOFTWARE_REVISION = (os.getenv("VERCEL_GIT_COMMIT_SHA") or os.getenv("IDP_SOFTWARE_REVISION") or "local-development")
POLICY_CONFIG = {"look_away_seconds": LOOK_AWAY_SECONDS, "response_time_ms": RESPONSE_TIME_MS, "cooldown_seconds": COOLDOWN_SECONDS}



def now_epoch() -> int:
    return int(time.time())


def get_session(conn, session_id: str):
    row = conn.execute(
        "SELECT s.*, p.code participant_code, l.payload lesson_payload FROM sessions s JOIN participants p ON p.id=s.participant_id JOIN lessons l ON l.id=s.lesson_id WHERE s.id=?",
        (session_id,),
    ).fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    return row


def require_session_token(conn, session_id: str, token: str | None):
    if hasattr(conn, "lock_session"):
        conn.lock_session(session_id)
    row = get_session(conn, session_id)
    if not token or token != row["access_token"]:
        raise HTTPException(401, "A valid session token is required")
    return row


def lesson_payload(conn, lesson_id: str) -> dict[str, Any]:
    row = conn.execute("SELECT payload FROM lessons WHERE id=?", (lesson_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Lesson not found")
    return json.loads(row["payload"])


def public_lesson(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip answer keys before lesson content reaches the browser."""
    result = json.loads(json.dumps(payload))
    for phase_questions in result.get("questions", {}).values():
        for question in phase_questions:
            question.pop("answer", None)
            question.pop("answer_explanation", None)
    return result


def find_question(payload: dict[str, Any], phase: str, question_id: str) -> dict[str, Any]:
    question = next((q for q in payload.get("questions", {}).get(phase, []) if q.get("id") == question_id), None)
    if not question:
        raise HTTPException(422, "Question does not belong to this lesson and phase")
    return question


def intervention_status(row: Any) -> str:
    return row["status"] if row["status"] else ("accepted" if row["accepted"] else "offered")


def approved_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Reject raw camera material anywhere; store only typed summary fields."""
    forbidden = {"frame", "image", "image_data", "raw_frame", "bitmap", "landmarks", "face_landmarks"}
    def inspect(value):
        if isinstance(value, dict):
            if forbidden.intersection(value):
                raise HTTPException(422, "Raw camera frames and landmarks must remain local to the browser")
            for item in value.values(): inspect(item)
        elif isinstance(value, list):
            for item in value: inspect(item)
    inspect(payload)
    from pydantic import ValidationError
    try:
        return EventPayload.model_validate(payload).model_dump(exclude_none=True)
    except ValidationError:
        raise HTTPException(422, "Invalid interaction or camera summary")


def canonical_interaction(conn, session, interaction):
    interaction = dict(interaction)
    interaction["concept"] = session["lesson_id"]
    recent = conn.execute("SELECT correct, response_time_ms FROM answers WHERE session_id=? AND phase='checkpoint' ORDER BY id DESC", (session["id"],)).fetchall()
    streak = 0
    for row in recent:
        if row["correct"]: break
        streak += 1
    interaction["incorrect_streak"] = streak
    interaction["quiz_correct"] = bool(recent[0]["correct"]) if recent else None
    interaction["response_time_ms"] = (recent[0]["response_time_ms"] or 0) if recent else 0
    visits = json.loads(session["section_visits"] or "{}")
    interaction["revisits"] = max(0, max(visits.values(), default=1) - 1)
    return interaction


def state_for(conn, session, payload: dict[str, Any]) -> dict[str, Any]:
    interaction = payload.get("interaction", {}) or {}
    signal = payload.get("signal_summary", {}) or {}
    reasons: list[str] = []
    observations: list[str] = []
    if interaction.get("help_requested"):
        reasons.append("The learner requested help")
    if int(interaction.get("incorrect_streak", 0)) >= 2:
        reasons.append("Two checkpoint answers were incorrect in a row")
    if interaction.get("quiz_correct") is False and (
        int(interaction.get("revisits", 0)) >= 2 or int(interaction.get("response_time_ms", 0)) >= RESPONSE_TIME_MS
    ):
        reasons.append("An incorrect answer was paired with repeated revisits or a long response")
    sustained = int(signal.get("sustained_seconds", 0) or 0)
    if signal.get("face_present") is False and sustained >= LOOK_AWAY_SECONDS:
        observations.append("No face was detected for a sustained period")
    if signal.get("looking_away") is True and sustained >= LOOK_AWAY_SECONDS:
        observations.append("Head orientation suggested looking away for a sustained period")

    triggered = bool(reasons)
    mode = session["mode"]
    if mode == "static":
        return {"level": "ok", "triggered": False, "reasons": [], "observations": observations, "intervention": None}

    active = conn.execute(
        "SELECT * FROM interventions WHERE session_id=? AND status IN ('offered','viewed','accepted') ORDER BY id DESC LIMIT 1",
        (session["id"],),
    ).fetchone()
    if active:
        item = dict(active)
        item["status"] = intervention_status(active)
        return {"level": "support_active", "triggered": False, "reasons": reasons, "observations": observations, "intervention": {"id": item["id"], "kind": item["kind"], "concept": item["concept"], "reason": item["reason"], "selection_reason": item["selection_reason"], "follow_up_bank": item["follow_up_bank"], "status": item["status"]}}

    last = conn.execute(
        "SELECT created_at FROM interventions WHERE session_id=? ORDER BY id DESC LIMIT 1", (session["id"],)
    ).fetchone()
    cooldown = False
    if last:
        try:
            last_dt = datetime.fromisoformat(str(last["created_at"]).replace("Z", "+00:00"))
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            cooldown = (datetime.now(timezone.utc) - last_dt).total_seconds() < COOLDOWN_SECONDS
        except ValueError:
            cooldown = False
    if cooldown and not interaction.get("help_requested"):
        triggered = False
        reasons.append("Automatic intervention cooldown is active")

    intervention = None
    selection_reason = "fixed policy"
    if triggered:
        concept = interaction.get("concept", "general")
        kind = choose_intervention(conn, session, concept, interaction)
        follow_up_bank = choose_follow_up_bank(conn, session, concept)
        if session["mode"] == "personalized":
            seen_kind = conn.execute(
                "SELECT 1 FROM personalization_aggregates WHERE participant_id=? AND reset_group=? AND mode='personalized' AND concept=? AND kind=? AND completed_interventions > 0 LIMIT 1",
                (session["participant_id"], session["reset_group"], concept, kind),
            ).fetchone()
            selection_reason = "best completed follow-up score" if seen_kind else "exploration of an unused support type"
        try:
            cursor = conn.execute(
                "INSERT INTO interventions (session_id, concept, kind, trigger, reason, selection_reason, follow_up_bank, status) VALUES (?, ?, ?, ?, ?, ?, ?, 'offered') RETURNING id",
                (session["id"], concept, kind, "help_request" if interaction.get("help_requested") else "difficulty_rule", " | ".join(reasons), selection_reason, follow_up_bank),
            )
            intervention = {"id": cursor.fetchone()["id"], "kind": kind, "concept": concept, "reason": " ".join(reasons), "selection_reason": selection_reason, "follow_up_bank": follow_up_bank, "status": "offered"}
        except Exception as exc:
            # Concurrent requests may hit the one-active-support index after
            # both observed an empty active set. Return the canonical row.
            if "idx_one_active_intervention" not in str(exc) and "UNIQUE" not in str(exc).upper():
                raise
            active = conn.execute(
                "SELECT * FROM interventions WHERE session_id=? AND status IN ('offered','viewed','accepted') ORDER BY id DESC LIMIT 1",
                (session["id"],),
            ).fetchone()
            if not active:
                raise
            intervention = {"id": active["id"], "kind": active["kind"], "concept": active["concept"], "reason": active["reason"], "selection_reason": active["selection_reason"], "follow_up_bank": active["follow_up_bank"], "status": intervention_status(active)}
            return {"level": "support_active", "triggered": False, "reasons": reasons, "observations": observations, "intervention": intervention}
    return {"level": "difficulty" if triggered else "ok", "triggered": triggered, "reasons": reasons, "observations": observations, "intervention": intervention}


def choose_intervention(conn, session, concept: str, interaction: dict[str, Any]) -> str:
    if session["mode"] == "rule_based":
        streak = int(interaction.get("incorrect_streak", 0))
        return "guided_practice" if streak >= 3 else ("worked_example" if streak >= 2 else "simplified")
    rows = conn.execute(
        """
        SELECT kind, outcome_sum, completed_interventions
        FROM personalization_aggregates
        WHERE participant_id=? AND mode='personalized' AND reset_group=? AND concept=?
        ORDER BY ((outcome_sum + 1.0) / (completed_interventions + 2.0)) DESC, completed_interventions DESC
        """,
        (session["participant_id"], session["reset_group"], concept),
    ).fetchall()
    seen = {row["kind"] for row in rows}
    for kind in INTERVENTIONS:
        if kind not in seen:
            return kind
    return rows[0]["kind"] if rows else "simplified"


def choose_follow_up_bank(conn, session, concept: str) -> str:
    """Use an equivalent question set when this participant revisits a concept."""
    repeated = conn.execute(
        """SELECT 1 FROM interventions i
           JOIN sessions s ON s.id=i.session_id
           WHERE s.participant_id=? AND s.reset_group=? AND i.concept=?
           LIMIT 1""",
        (session["participant_id"], session["reset_group"], concept),
    ).fetchone()
    return "follow_up_repeat" if repeated else "follow_up"


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "adaptive-learning"}


@app.get("/health/live")
def health_live():
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    if (os.getenv("IDP_ENV") == "production" or os.getenv("VERCEL")) and (not DATABASE_URL or not os.getenv("IDP_RESEARCHER_TOKEN")):
        raise HTTPException(503, "Database and researcher credential must be configured")
    with connect() as conn:
        if not conn.execute("SELECT id FROM lessons LIMIT 1").fetchone():
            raise HTTPException(503, "Database has not been prepared")
    return {"status": "ready", "software_revision": SOFTWARE_REVISION}


def require_researcher(token: str | None):
    expected = os.getenv("IDP_RESEARCHER_TOKEN")
    if not expected and os.getenv("IDP_ENV", "local") != "production" and not os.getenv("VERCEL"):
        expected = "local-researcher"
    if not expected or not token or not secrets.compare_digest(token, expected):
        raise HTTPException(401, "A valid researcher credential is required")


@app.get("/api/research/sessions")
def research_sessions(x_researcher_token: str | None = Header(default=None)):
    require_researcher(x_researcher_token)
    with connect() as conn:
        rows = conn.execute("""
            SELECT s.id session_id, p.code participant_code, s.mode, s.study_kind,
                   s.lesson_id, s.data_origin, s.content_version, s.policy_version,
                   s.reset_group, s.started_at, s.ended_at,
                   COUNT(DISTINCT a.id) answer_count, COUNT(DISTINCT i.id) intervention_count
            FROM sessions s JOIN participants p ON p.id=s.participant_id
            LEFT JOIN answers a ON a.session_id=s.id
            LEFT JOIN interventions i ON i.session_id=s.id
            GROUP BY s.id, p.code
            ORDER BY s.started_at DESC
        """).fetchall()
        return [dict(row) for row in rows]


@app.get("/api/research/assignments")
def research_assignments(x_researcher_token: str | None = Header(default=None)):
    """Return the fixed pilot rotation without exposing participant session data."""
    require_researcher(x_researcher_token)
    return {"content_version": CONTENT_VERSION, "policy_version": POLICY_VERSION, "assignments": PILOT_ASSIGNMENTS}


@app.post("/api/research/participants/{participant_code}/reset")
def reset_personalization(participant_code: str, x_researcher_token: str | None = Header(default=None)):
    require_researcher(x_researcher_token)
    boundary = uuid.uuid4().hex
    with connect() as conn:
        result = conn.execute("UPDATE participants SET reset_group=? WHERE code=?", (boundary, participant_code))
        if result.rowcount == 0:
            raise HTTPException(404, "Participant not found")
        return {"participant_code": participant_code, "reset_group": boundary, "reset": True}


@app.get("/api/research/export.csv")
def research_export(x_researcher_token: str | None = Header(default=None)):
    require_researcher(x_researcher_token)
    with connect() as conn:
        rows = conn.execute("""
            SELECT s.id session_id, p.code participant_code, s.mode, s.study_kind, s.lesson_id,
                   s.data_origin, s.content_version, s.policy_version, s.reset_group,
                   s.started_at, s.ended_at, a.phase, a.concept, a.correct,
                   a.response_time_ms, NULL AS intervention_kind, NULL AS intervention_status,
                   NULL AS follow_up_correct, NULL AS helpfulness,
                   s.active_time_ms, s.elapsed_time_ms, s.camera_consent
            FROM sessions s JOIN participants p ON p.id=s.participant_id
            LEFT JOIN answers a ON a.session_id=s.id
            UNION ALL
            SELECT s.id, p.code, s.mode, s.study_kind, s.lesson_id, s.data_origin,
                   s.content_version, s.policy_version, s.reset_group, s.started_at, s.ended_at,
                   'intervention', i.concept, NULL, NULL, i.kind, i.status, NULL, NULL,
                   s.active_time_ms, s.elapsed_time_ms, s.camera_consent
            FROM sessions s JOIN participants p ON p.id=s.participant_id
            JOIN interventions i ON i.session_id=s.id
            UNION ALL
            SELECT s.id, p.code, s.mode, s.study_kind, s.lesson_id, s.data_origin,
                   s.content_version, s.policy_version, s.reset_group, s.started_at, s.ended_at,
                   'follow_up', i.concept, f.correct, NULL, i.kind, i.status, f.correct, f.helpfulness
                   , s.active_time_ms, s.elapsed_time_ms, s.camera_consent
            FROM sessions s JOIN participants p ON p.id=s.participant_id
            JOIN interventions i ON i.session_id=s.id
            JOIN follow_ups f ON f.intervention_id=i.id
            ORDER BY started_at DESC
        """).fetchall()
        output = io.StringIO(); writer = csv.writer(output)
        writer.writerow(["session_id", "participant_code", "mode", "study_kind", "lesson_id", "data_origin", "content_version", "policy_version", "reset_group", "started_at", "ended_at", "record_type", "concept", "correct", "response_time_ms", "intervention_kind", "intervention_status", "follow_up_correct", "helpfulness", "active_time_ms", "elapsed_time_ms", "camera_consent", "signal_face_present", "signal_ambiguous", "signal_looking_away", "signal_blink_count", "signal_status", "feedback_support_helpfulness", "feedback_usability_rating", "feedback_ease_rating", "feedback_comment", "signal_gaze_direction", "signal_head_yaw_degrees", "signal_head_pitch_degrees", "signal_head_roll_degrees"])
        for row in rows: writer.writerow([row[key] if row[key] is not None else "" for key in row.keys()] + ["", "", "", "", "", "", "", "", "", "", "", "", ""])
        for event in conn.execute("SELECT s.id session_id, p.code participant_code, s.mode, s.study_kind, s.lesson_id, s.data_origin, s.content_version, s.policy_version, s.reset_group, s.started_at, s.ended_at, s.active_time_ms, s.elapsed_time_ms, s.camera_consent, e.payload FROM sessions s JOIN participants p ON p.id=s.participant_id JOIN events e ON e.session_id=s.id WHERE e.event_type='signal_summary' ORDER BY e.id").fetchall():
            signal = json.loads(event["payload"]).get("signal_summary", {}) or {}
            writer.writerow([event["session_id"], event["participant_code"], event["mode"], event["study_kind"], event["lesson_id"], event["data_origin"], event["content_version"], event["policy_version"], event["reset_group"], event["started_at"], event["ended_at"], "signal_summary", "", "", "", "", "", "", "", event["active_time_ms"], event["elapsed_time_ms"], event["camera_consent"], signal.get("face_present", ""), signal.get("ambiguous", ""), signal.get("looking_away", ""), signal.get("blink_count", ""), signal.get("status", ""), "", "", "", "", signal.get("gaze_direction", ""), signal.get("head_yaw_degrees", ""), signal.get("head_pitch_degrees", ""), signal.get("head_roll_degrees", "")])
        for feedback in conn.execute("SELECT s.id session_id, p.code participant_code, s.mode, s.study_kind, s.lesson_id, s.data_origin, s.content_version, s.policy_version, s.reset_group, s.started_at, s.ended_at, s.active_time_ms, s.elapsed_time_ms, s.camera_consent, f.id feedback_id, f.support_helpfulness, f.usability_rating, f.ease_rating, f.comment FROM session_feedback f JOIN sessions s ON s.id=f.session_id JOIN participants p ON p.id=s.participant_id ORDER BY f.id").fetchall():
            writer.writerow([feedback["session_id"], feedback["participant_code"], feedback["mode"], feedback["study_kind"], feedback["lesson_id"], feedback["data_origin"], feedback["content_version"], feedback["policy_version"], feedback["reset_group"], feedback["started_at"], feedback["ended_at"], "feedback", "", "", "", "", "", "", "", feedback["active_time_ms"], feedback["elapsed_time_ms"], feedback["camera_consent"], "", "", "", "", "", feedback["support_helpfulness"] or "", feedback["usability_rating"] or "", feedback["ease_rating"] or "", feedback["comment"] or "", "", "", "", ""])
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=study-export.csv"})


@app.get("/api/lessons")
def lessons():
    with connect() as conn:
        rows = conn.execute("SELECT payload FROM lessons ORDER BY id").fetchall()
        return [public_lesson(json.loads(row["payload"])) for row in rows]


@app.post("/api/sessions")
def create_session(body: SessionCreate, x_researcher_token: str | None = Header(default=None)):
    demo_token = None
    code = body.participant_code.strip()
    if not code or code.startswith("demo:"):
        raise HTTPException(422, "Use a nonempty participant code without a reserved prefix")
    if body.study_kind == "demo":
        demo_token = body.demo_token or secrets.token_urlsafe(32)
        code = "demo:" + hashlib.sha256(demo_token.encode()).hexdigest()[:24]
    else:
        require_researcher(x_researcher_token)
    with connect() as conn:
        lesson = conn.execute("SELECT id FROM lessons WHERE id=?", (body.lesson_id,)).fetchone()
        if not lesson:
            raise HTTPException(404, "Lesson not found")
        participant = conn.execute("SELECT id, reset_group FROM participants WHERE code=?", (code,)).fetchone()
        if not participant:
            cursor = conn.execute("INSERT INTO participants (code) VALUES (?) RETURNING id", (code,))
            participant_id = cursor.fetchone()["id"]
            reset_group = "default"
        else:
            participant_id = participant["id"]
            reset_group = participant["reset_group"]
        session_id = uuid.uuid4().hex
        access_token = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO sessions (id, participant_id, mode, lesson_id, access_token, study_kind, camera_consent, content_version, policy_version, reset_group, progress_phase, data_origin, software_revision, policy_config) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, participant_id, body.mode, body.lesson_id, access_token, body.study_kind, int(body.camera_consent), CONTENT_VERSION, POLICY_VERSION, reset_group, "retention" if body.study_kind == "retention" else "pre" if body.study_kind == "study" else "learn", "synthetic_demo" if body.study_kind == "demo" else "observed", SOFTWARE_REVISION, json.dumps(POLICY_CONFIG)),
        )
        return {"session_id": session_id, "access_token": access_token, "participant_code": code, "demo_token": demo_token, "software_revision": SOFTWARE_REVISION, "policy_config": POLICY_CONFIG, "mode": body.mode, "lesson_id": body.lesson_id, "study_kind": body.study_kind, "camera_consent": body.camera_consent, "content_version": CONTENT_VERSION, "policy_version": POLICY_VERSION}


@app.get("/api/sessions/{session_id}")
def session_detail(session_id: str, x_session_token: str | None = Header(default=None)):
    with connect() as conn:
        session = require_session_token(conn, session_id, x_session_token)
        answers = [dict(row) for row in conn.execute("SELECT * FROM answers WHERE session_id=? ORDER BY id", (session_id,)).fetchall()]
        interventions = []
        for row in conn.execute("SELECT * FROM interventions WHERE session_id=? ORDER BY id", (session_id,)).fetchall():
            item = dict(row)
            item["follow_ups"] = [dict(f) for f in conn.execute("SELECT * FROM follow_ups WHERE intervention_id=? ORDER BY id", (row["id"],)).fetchall()]
            interventions.append(item)
        events = []
        for row in conn.execute("SELECT id, event_type, payload, created_at FROM events WHERE session_id=? ORDER BY id", (session_id,)).fetchall():
            item = dict(row)
            item["payload"] = json.loads(item["payload"])
            events.append(item)
        feedback_row = conn.execute("SELECT id, support_helpfulness, usability_rating, ease_rating, comment, created_at FROM session_feedback WHERE session_id=?", (session_id,)).fetchone()
        return {
            "id": session_id,
            "participant_code": session["participant_code"],
            "mode": session["mode"],
            "lesson_id": session["lesson_id"],
            "study_kind": session["study_kind"],
            "data_origin": session["data_origin"],
            "camera_consent": bool(session["camera_consent"]),
            "software_revision": session["software_revision"], "policy_config": json.loads(session["policy_config"]), "ended_at": session["ended_at"],
            "content_version": session["content_version"],
            "policy_version": session["policy_version"],
            "progress": {"phase": session["progress_phase"], "question_id": session["progress_question_id"], "question_index": session["progress_question_index"], "section_id": session["progress_section_id"], "section_visits": json.loads(session["section_visits"] or "{}"), "active_time_ms": session["active_time_ms"], "elapsed_time_ms": session["elapsed_time_ms"]},
            "answers": answers,
            "interventions": interventions,
            "events": events,
            "feedback": dict(feedback_row) if feedback_row else None,
        }


@app.get("/api/sessions/{session_id}/support-history")
def support_history(session_id: str, x_session_token: str | None = Header(default=None)):
    """Expose the participant's completed history without revealing other sessions."""
    with connect() as conn:
        session = require_session_token(conn, session_id, x_session_token)
        rows = conn.execute(
            """SELECT concept, kind, completed_interventions, outcome_sum
               FROM personalization_aggregates
               WHERE participant_id=? AND reset_group=? AND mode='personalized'
               ORDER BY concept, kind""",
            (session["participant_id"], session["reset_group"]),
        ).fetchall()
        return [{**dict(row), "smoothed_score": round((row["outcome_sum"] + 1) / (row["completed_interventions"] + 2), 3)} for row in rows]


@app.post("/api/sessions/{session_id}/feedback")
def add_feedback(session_id: str, body: FeedbackCreate, x_session_token: str | None = Header(default=None)):
    with connect() as conn:
        session = require_session_token(conn, session_id, x_session_token)
        if body.support_helpfulness is None and body.usability_rating is None and body.ease_rating is None and not (body.comment or "").strip():
            raise HTTPException(422, "Provide a rating or comment")
        existing = conn.execute("SELECT id, support_helpfulness, usability_rating, ease_rating, comment, created_at FROM session_feedback WHERE session_id=?", (session_id,)).fetchone()
        if existing:
            return {"saved": True, "deduplicated": True, "feedback": dict(existing)}
        conn.execute(
            "INSERT INTO session_feedback (session_id, support_helpfulness, usability_rating, ease_rating, comment) VALUES (?, ?, ?, ?, ?)",
            (session_id, body.support_helpfulness, body.usability_rating, body.ease_rating, body.comment.strip() if body.comment else None),
        )
        saved = conn.execute("SELECT id, support_helpfulness, usability_rating, ease_rating, comment, created_at FROM session_feedback WHERE session_id=?", (session_id,)).fetchone()
        return {"saved": True, "deduplicated": False, "feedback": dict(saved)}


@app.get("/api/sessions/{session_id}/resume")
def resume_session(session_id: str, x_session_token: str | None = Header(default=None)):
    """Return the persisted session state needed to resume after a reload."""
    with connect() as conn:
        session = require_session_token(conn, session_id, x_session_token)
        return {"id": session_id, "access_token": session["access_token"], "progress": {"phase": session["progress_phase"], "question_id": session["progress_question_id"], "question_index": session["progress_question_index"], "section_id": session["progress_section_id"], "section_visits": json.loads(session["section_visits"] or "{}"), "active_time_ms": session["active_time_ms"], "elapsed_time_ms": session["elapsed_time_ms"]}, "ended": bool(session["ended_at"])}


@app.post("/api/sessions/{session_id}/progress")
def update_progress(session_id: str, body: ProgressUpdate, x_session_token: str | None = Header(default=None)):
    with connect() as conn:
        session = require_session_token(conn, session_id, x_session_token)
        if session["ended_at"]:
            raise HTTPException(409, "Session is already complete")
        payload = json.loads(session["lesson_payload"])
        if body.question_id:
            find_question(payload, body.phase, body.question_id)
        if body.section_id not in {section.get("id") for section in payload.get("sections", [])}:
            raise HTTPException(422, "Section does not belong to this lesson")
        section_visits = {key: value for key, value in body.section_visits.items() if value >= 0}
        conn.execute("UPDATE sessions SET progress_phase=?, progress_question_id=?, progress_question_index=?, progress_section_id=?, section_visits=?, active_time_ms=?, elapsed_time_ms=? WHERE id=? AND ended_at IS NULL", (body.phase, body.question_id, body.question_index, body.section_id, json.dumps(section_visits), max(session["active_time_ms"], body.active_time_ms), max(session["elapsed_time_ms"], body.elapsed_time_ms), session_id))
        row = conn.execute("SELECT progress_phase, progress_question_id, progress_question_index, progress_section_id, section_visits, active_time_ms, elapsed_time_ms FROM sessions WHERE id=?", (session_id,)).fetchone()
        return {"saved": True, "progress": {"phase": row["progress_phase"], "question_id": row["progress_question_id"], "question_index": row["progress_question_index"], "section_id": row["progress_section_id"], "section_visits": json.loads(row["section_visits"] or "{}"), "active_time_ms": row["active_time_ms"], "elapsed_time_ms": row["elapsed_time_ms"]}}


@app.post("/api/sessions/{session_id}/events")
def add_event(session_id: str, body: EventCreate, x_session_token: str | None = Header(default=None)):
    with connect() as conn:
        session = require_session_token(conn, session_id, x_session_token)
        if session["ended_at"]:
            raise HTTPException(409, "Session is already complete")
        existing = conn.execute("SELECT decision_json FROM events WHERE session_id=? AND client_event_id=?", (session_id, body.client_event_id)).fetchone()
        if existing and existing["decision_json"]:
            return {"event_accepted": True, "deduplicated": True, "state": json.loads(existing["decision_json"])}
        event_payload = approved_event_payload(body.payload)
        event_payload["interaction"] = canonical_interaction(conn, session, event_payload.get("interaction", {}))
        if not session["camera_consent"]:
            event_payload.pop("signal_summary", None)
        try:
            conn.execute("INSERT INTO events (session_id, client_event_id, event_type, payload) VALUES (?, ?, ?, ?)", (session_id, body.client_event_id, body.event_type, json.dumps(event_payload)))
        except Exception as exc:
            if "UNIQUE" not in str(exc).upper():
                raise
            existing = conn.execute("SELECT decision_json FROM events WHERE session_id=? AND client_event_id=?", (session_id, body.client_event_id)).fetchone()
            if existing and existing["decision_json"]:
                return {"event_accepted": True, "deduplicated": True, "state": json.loads(existing["decision_json"])}
        state = state_for(conn, session, event_payload)
        conn.execute("UPDATE events SET decision_json=? WHERE session_id=? AND client_event_id=?", (json.dumps(state), session_id, body.client_event_id))
        return {"event_accepted": True, "deduplicated": False, "state": state}


@app.post("/api/sessions/{session_id}/answers")
def add_answer(session_id: str, body: AnswerCreate, x_session_token: str | None = Header(default=None)):
    with connect() as conn:
        session = require_session_token(conn, session_id, x_session_token)
        if session["ended_at"]:
            raise HTTPException(409, "Session is already complete")
        payload = json.loads(session["lesson_payload"])
        question = find_question(payload, body.phase, body.question_id)
        if body.concept != question.get("concept"):
            raise HTTPException(422, "Question concept does not match the lesson")
        if body.answer not in question.get("options", []):
            raise HTTPException(422, "Answer is not a valid option for this question")
        existing = conn.execute(
            "SELECT correct FROM answers WHERE session_id=? AND question_id=? AND phase=?",
            (session_id, body.question_id, body.phase),
        ).fetchone()
        if existing:
            # A retry must return the canonical saved result.  Never allow a
            # second request to regrade or overwrite an assessment response.
            recent = conn.execute(
                "SELECT correct, concept FROM answers WHERE session_id=? AND phase='checkpoint' AND concept=? ORDER BY id DESC",
                (session_id, body.concept),
            ).fetchall()
            incorrect_streak = 0
            for saved in recent:
                if saved["correct"] == 0:
                    incorrect_streak += 1
                else:
                    break
            saved_timing = conn.execute(
                "SELECT response_time_ms FROM answers WHERE session_id=? AND question_id=? AND phase=?",
                (session_id, body.question_id, body.phase),
            ).fetchone()
            return {"saved": True, "deduplicated": True, "correct": bool(existing["correct"]), "incorrect_streak": incorrect_streak, "response_time_ms": saved_timing["response_time_ms"] if saved_timing else None}
        correct = body.answer == question.get("answer")
        measured_response_ms = body.response_time_ms
        if body.response_started_at:
            try:
                started = datetime.fromisoformat(body.response_started_at.replace("Z", "+00:00"))
                if started.tzinfo is None:
                    started = started.replace(tzinfo=timezone.utc)
                measured_response_ms = max(0, int((datetime.now(timezone.utc) - started.astimezone(timezone.utc)).total_seconds() * 1000))
            except ValueError:
                measured_response_ms = body.response_time_ms
        conn.execute(
            "INSERT INTO answers (session_id, question_id, phase, concept, answer, correct, response_time_ms, response_started_at, submitted_at, section_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)",
            (session_id, body.question_id, body.phase, body.concept, body.answer, int(correct), measured_response_ms, body.response_started_at, body.section_id),
        )
        streak = conn.execute("SELECT correct, concept FROM answers WHERE session_id=? AND phase='checkpoint' AND concept=? ORDER BY id DESC", (session_id, body.concept)).fetchall()
        # A streak is consecutive from the newest checkpoint backwards.  A
        # wrong answer followed by a correct answer must reset the streak.
        incorrect_streak = 0
        for row in streak:
            if row["correct"] == 0:
                incorrect_streak += 1
            else:
                break
        return {"saved": True, "deduplicated": False, "correct": correct, "incorrect_streak": incorrect_streak, "response_time_ms": measured_response_ms}


@app.post("/api/sessions/{session_id}/interventions/{intervention_id}/response")
def respond_intervention(session_id: str, intervention_id: int, body: InterventionResponse, x_session_token: str | None = Header(default=None)):
    with connect() as conn:
        session = require_session_token(conn, session_id, x_session_token)
        if session["ended_at"]:
            raise HTTPException(409, "Session is already complete")
        row = conn.execute("SELECT * FROM interventions WHERE id=? AND session_id=?", (intervention_id, session_id)).fetchone()
        if not row:
            raise HTTPException(404, "Intervention not found")
        if row["status"] in ("completed", "dismissed", "skipped"):
            return {"saved": True, "status": row["status"], "deduplicated": True}
        transitions = {
            "view": ("viewed", "viewed_at"),
            "accept": ("accepted", "accepted"),
            "dismiss": ("dismissed", "dismissed_at"),
            "skip": ("skipped", "skipped_at"),
        }
        status, timestamp_column = transitions[body.action]
        if timestamp_column == "accepted":
            conn.execute("UPDATE interventions SET accepted=1, status='accepted', viewed_at=COALESCE(viewed_at, CAST(CURRENT_TIMESTAMP AS TEXT)) WHERE id=?", (intervention_id,))
        elif timestamp_column == "viewed_at":
            conn.execute("UPDATE interventions SET status=CASE WHEN status='offered' THEN 'viewed' ELSE status END, viewed_at=COALESCE(viewed_at, CAST(CURRENT_TIMESTAMP AS TEXT)) WHERE id=?", (intervention_id,))
        else:
            conn.execute(f"UPDATE interventions SET status=?, {timestamp_column}=CURRENT_TIMESTAMP, accepted=? WHERE id=?", (status, 0, intervention_id))
        updated = conn.execute("SELECT status, accepted FROM interventions WHERE id=?", (intervention_id,)).fetchone()
        return {"saved": True, "status": updated["status"], "accepted": updated["accepted"]}


@app.post("/api/sessions/{session_id}/interventions/{intervention_id}/follow-ups")
def add_follow_up(session_id: str, intervention_id: int, body: FollowUpCreate, x_session_token: str | None = Header(default=None)):
    with connect() as conn:
        session = require_session_token(conn, session_id, x_session_token)
        if session["ended_at"]:
            raise HTTPException(409, "Session is already complete")
        intervention = conn.execute("SELECT * FROM interventions WHERE id=? AND session_id=?", (intervention_id, session_id)).fetchone()
        row = intervention
        if not row:
            raise HTTPException(404, "Intervention not found")
        if row["status"] not in ("accepted", "completed") or not row["accepted"]:
            raise HTTPException(409, "Accept the support before submitting follow-up checks")
        existing_follow_up = conn.execute(
            "SELECT correct, helpfulness FROM follow_ups WHERE intervention_id=? AND question_id=?",
            (intervention_id, body.question_id),
        ).fetchone()
        if existing_follow_up:
            count = conn.execute("SELECT COUNT(*) AS count FROM follow_ups WHERE intervention_id=?", (intervention_id,)).fetchone()["count"]
            return {"saved": True, "deduplicated": True, "correct": bool(existing_follow_up["correct"]), "completed_follow_ups": count, "helpfulness": existing_follow_up["helpfulness"]}
        existing_count = conn.execute("SELECT COUNT(*) AS count FROM follow_ups WHERE intervention_id=?", (intervention_id,)).fetchone()["count"]
        if existing_count >= 2:
            raise HTTPException(409, "This support item already has two follow-up checks")
        payload = json.loads(session["lesson_payload"])
        bank = intervention["follow_up_bank"] or "follow_up"
        question = next((q for q in payload.get("questions", {}).get(bank, []) if q.get("id") == body.question_id), None)
        if not question or question.get("concept") != intervention["concept"] or body.answer not in question.get("options", []):
            raise HTTPException(422, "Follow-up question or answer is invalid")
        correct = body.answer == question.get("answer")
        conn.execute("INSERT INTO follow_ups (intervention_id, question_id, answer, correct, helpfulness) VALUES (?, ?, ?, ?, ?)", (intervention_id, body.question_id, body.answer, int(correct), body.helpfulness))
        count = conn.execute("SELECT COUNT(*) AS count FROM follow_ups WHERE intervention_id=?", (intervention_id,)).fetchone()["count"]
        if count >= 2:
            conn.execute("UPDATE interventions SET status='completed', completed_at=CURRENT_TIMESTAMP WHERE id=? AND accepted=1", (intervention_id,))
            if session["mode"] == "personalized":
                outcome_sum = conn.execute("SELECT COALESCE(SUM(correct), 0) / 2.0 AS score FROM follow_ups WHERE intervention_id=?", (intervention_id,)).fetchone()["score"]
                conn.execute(
                    """INSERT INTO personalization_aggregates
                       (participant_id, reset_group, mode, concept, kind, completed_interventions, outcome_sum)
                       VALUES (?, ?, ?, ?, ?, 1, ?)
                       ON CONFLICT(participant_id, reset_group, mode, concept, kind)
                       DO UPDATE SET completed_interventions=personalization_aggregates.completed_interventions + excluded.completed_interventions,
                                     outcome_sum=personalization_aggregates.outcome_sum + excluded.outcome_sum,
                                     updated_at=CURRENT_TIMESTAMP""",
                    (session["participant_id"], session["reset_group"], session["mode"], intervention["concept"], intervention["kind"], outcome_sum),
                )
        return {"saved": True, "deduplicated": False, "correct": correct, "completed_follow_ups": count}


@app.post("/api/sessions/{session_id}/end")
def end_session(session_id: str, x_session_token: str | None = Header(default=None)):
    with connect() as conn:
        require_session_token(conn, session_id, x_session_token)
        conn.execute("UPDATE sessions SET ended_at=CURRENT_TIMESTAMP WHERE id=?", (session_id,))
        return {"ended": True}


@app.get("/api/sessions/{session_id}/export.csv")
def export_csv(session_id: str, x_session_token: str | None = Header(default=None)):
    with connect() as conn:
        session = require_session_token(conn, session_id, x_session_token)
        output = io.StringIO()
        writer = csv.writer(output)
        meta = [session_id, session["participant_code"], session["mode"], session["study_kind"], session["lesson_id"], session["data_origin"], session["content_version"], session["policy_version"], session["reset_group"]]
        completeness = "complete" if session["ended_at"] else "in_progress"
        writer.writerow(["record_type", "id", "session_id", "participant_code", "mode", "study_kind", "lesson_id", "data_origin", "content_version", "policy_version", "reset_group", "phase", "concept", "kind", "correct", "response_time_ms", "reason", "intervention_status", "follow_up_correct", "helpfulness", "completeness", "active_time_ms", "elapsed_time_ms", "camera_consent", "signal_face_present", "signal_ambiguous", "signal_looking_away", "signal_blink_count", "signal_status", "feedback_support_helpfulness", "feedback_usability_rating", "feedback_ease_rating", "feedback_comment", "signal_gaze_direction", "signal_head_yaw_degrees", "signal_head_pitch_degrees", "signal_head_roll_degrees"])
        for row in conn.execute("SELECT * FROM answers WHERE session_id=? ORDER BY id", (session_id,)).fetchall():
            writer.writerow(["answer", row["id"], *meta, row["phase"], row["concept"], "", row["correct"], row["response_time_ms"] or "", "", "", "", "", completeness, session["active_time_ms"], session["elapsed_time_ms"], session["camera_consent"], "", "", "", "", "", "", "", "", "", "", "", "", ""])
        for row in conn.execute("SELECT * FROM interventions WHERE session_id=? ORDER BY id", (session_id,)).fetchall():
            writer.writerow(["intervention", row["id"], *meta, "", row["concept"], row["kind"], "", "", row["reason"], row["status"], "", "", completeness, session["active_time_ms"], session["elapsed_time_ms"], session["camera_consent"], "", "", "", "", "", "", "", "", "", "", "", "", ""])
        for row in conn.execute("SELECT f.* FROM follow_ups f JOIN interventions i ON i.id=f.intervention_id WHERE i.session_id=? ORDER BY f.id", (session_id,)).fetchall():
            writer.writerow(["follow_up", row["id"], *meta, "follow_up", "", "", row["correct"], "", "", "", row["correct"], row["helpfulness"] or "", completeness, session["active_time_ms"], session["elapsed_time_ms"], session["camera_consent"], "", "", "", "", "", "", "", "", "", "", "", "", ""])
        for event in conn.execute("SELECT id, payload FROM events WHERE session_id=? AND event_type='signal_summary' ORDER BY id", (session_id,)).fetchall():
            signal = json.loads(event["payload"]).get("signal_summary", {}) or {}
            writer.writerow(["signal_summary", event["id"], *meta, "signal_summary", "", "", "", "", "", "", "", "", completeness, session["active_time_ms"], session["elapsed_time_ms"], session["camera_consent"], signal.get("face_present", ""), signal.get("ambiguous", ""), signal.get("looking_away", ""), signal.get("blink_count", ""), signal.get("status", ""), "", "", "", "", signal.get("gaze_direction", ""), signal.get("head_yaw_degrees", ""), signal.get("head_pitch_degrees", ""), signal.get("head_roll_degrees", "")])
        feedback = conn.execute("SELECT * FROM session_feedback WHERE session_id=?", (session_id,)).fetchone()
        if feedback:
            writer.writerow(["feedback", feedback["id"], *meta, "", "", "", "", "", "", "", "", "", completeness, session["active_time_ms"], session["elapsed_time_ms"], session["camera_consent"], "", "", "", "", "", feedback["support_helpfulness"] or "", feedback["usability_rating"] or "", feedback["ease_rating"] or "", feedback["comment"] or "", "", "", "", ""])
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={session_id}.csv"})
