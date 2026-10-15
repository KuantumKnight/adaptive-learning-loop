import os
import sys
import uuid
from pathlib import Path

os.environ["IDP_DB_PATH"] = str(Path(__file__).parent / "test.sqlite3")
sys.path.insert(0, str(Path(__file__).parents[2]))

from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import connect


class ResearchClient(TestClient):
    """Authenticated facilitator client for legacy measured/practice scenarios."""
    def post(self, url, **kwargs):
        if url == "/api/sessions":
            kwargs["json"] = {"study_kind": "practice", **kwargs.get("json", {})}
            kwargs["headers"] = {**kwargs.get("headers", {}), "X-Researcher-Token": "local-researcher"}
        return super().post(url, **kwargs)


def submit_wrong_checkpoints(client, session, count=2, response_time_ms=1000):
    with connect() as conn:
        lesson = __import__("json").loads(conn.execute("SELECT payload FROM lessons WHERE id=?", (session["lesson_id"],)).fetchone()["payload"])
    for question in lesson["questions"]["checkpoint"][:count]:
        wrong = next(option for option in question["options"] if option != question["answer"])
        response = client.post(f"/api/sessions/{session['session_id']}/answers", headers=auth(session), json={"question_id": question["id"], "phase": "checkpoint", "concept": question["concept"], "answer": wrong, "response_time_ms": response_time_ms})
        assert response.status_code == 200


def auth(session):
    return {"X-Session-Token": session["access_token"]}


def test_practice_opens_at_lesson_while_measured_study_keeps_baseline():
    with ResearchClient(app) as client:
        for study_kind, expected_phase in (("practice", "learn"), ("study", "pre")):
            session = client.post(
                "/api/sessions",
                json={
                    "participant_code": f"entry-{study_kind}-" + uuid.uuid4().hex[:8],
                    "mode": "static",
                    "lesson_id": "binary-search",
                    "study_kind": study_kind,
                },
            ).json()
            detail = client.get(
                f"/api/sessions/{session['session_id']}", headers=auth(session)
            ).json()
            assert detail["progress"]["phase"] == expected_phase


def test_closed_loop_and_idempotent_events():
    with ResearchClient(app) as client:
        lessons = client.get("/api/lessons").json()
        assert {lesson["id"] for lesson in lessons} == {"linear-search", "binary-search", "bubble-sort"}
        assert all(
            len(lesson["questions"]["pre"]) == 3
            and len(lesson["questions"]["checkpoint"]) == 6
            and len(lesson["questions"]["post"]) == 3
            and len(lesson["questions"]["follow_up"]) == 2
            and len(lesson["questions"]["follow_up_repeat"]) == 2
            and len(lesson["questions"]["retention"]) == 3
            for lesson in lessons
        )
        session = client.post("/api/sessions", json={"participant_code": "test-01", "mode": "personalized", "lesson_id": "binary-search"}).json()
        sid = session["session_id"]
        submit_wrong_checkpoints(client, session)
        payload = {"client_event_id": "fixed-event", "event_type": "difficulty_detected", "payload": {"interaction": {"concept": "binary-search", "incorrect_streak": 2, "quiz_correct": False}, "signal_summary": {"enabled": False}}}
        response = client.post(f"/api/sessions/{sid}/events", headers=auth(session), json=payload)
        assert response.status_code == 200
        assert response.json()["state"]["intervention"]["kind"] == "simplified"
        duplicate = client.post(f"/api/sessions/{sid}/events", headers=auth(session), json=payload)
        assert duplicate.status_code == 200 and duplicate.json()["deduplicated"] is True
        detail = client.get(f"/api/sessions/{sid}", headers=auth(session)).json()
        assert len(detail["interventions"]) == 1


def test_static_mode_does_not_intervene():
    with ResearchClient(app) as client:
        session = client.post("/api/sessions", json={"participant_code": "test-static", "mode": "static", "lesson_id": "linear-search"}).json()
        payload = {"client_event_id": "static-event", "event_type": "difficulty_detected", "payload": {"interaction": {"concept": "linear-search", "incorrect_streak": 4}, "signal_summary": {}}}
        state = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json=payload).json()["state"]
        assert state["intervention"] is None


def test_explicit_help_request_triggers_support():
    with ResearchClient(app) as client:
        session = client.post("/api/sessions", json={"participant_code": "test-help", "mode": "rule_based", "lesson_id": "bubble-sort"}).json()
        payload = {"client_event_id": "help-event", "event_type": "help_requested", "payload": {"interaction": {"concept": "bubble-sort", "help_requested": True}, "signal_summary": {}}}
        state = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json=payload).json()["state"]
        assert state["intervention"]["kind"] == "simplified"


def test_server_grades_answers_and_hides_keys():
    with ResearchClient(app) as client:
        lessons = client.get("/api/lessons").json()
        lesson = next(item for item in lessons if item["id"] == "linear-search")
        question = lesson["questions"]["pre"][0]
        assert "answer" not in question
        session = client.post("/api/sessions", json={"participant_code": "test-grade", "mode": "static", "lesson_id": "linear-search"}).json()
        result = client.post(f"/api/sessions/{session['session_id']}/answers", headers=auth(session), json={"question_id": question["id"], "phase": "pre", "concept": question["concept"], "answer": question["options"][0], "response_time_ms": 1420})
        assert result.status_code == 200
        assert result.json()["correct"] is True
        detail = client.get(f"/api/sessions/{session['session_id']}", headers=auth(session)).json()
        assert detail["answers"][0]["response_time_ms"] == 1420


def test_retention_session_starts_in_retention_phase_and_grades_retention_questions():
    with ResearchClient(app) as client:
        session = client.post(
            "/api/sessions",
            json={
                "participant_code": "retention-" + uuid.uuid4().hex[:8],
                "mode": "static",
                "lesson_id": "binary-search",
                "study_kind": "retention",
            },
        ).json()
        detail = client.get(
            f"/api/sessions/{session['session_id']}", headers=auth(session)
        ).json()
        assert detail["study_kind"] == "retention"
        assert detail["progress"]["phase"] == "retention"
        question = client.get("/api/lessons").json()[0]["questions"]["retention"][0]
        answer = client.post(
            f"/api/sessions/{session['session_id']}/answers",
            headers=auth(session),
            json={
                "question_id": question["id"],
                "phase": "retention",
                "concept": question["concept"],
                "answer": question["options"][0],
            },
        )
        assert answer.status_code == 200
        assert answer.json()["correct"] is True


def test_checkpoint_streak_resets_after_correct_answer():
    with ResearchClient(app) as client:
        session = client.post("/api/sessions", json={"participant_code": "test-streak", "mode": "rule_based", "lesson_id": "linear-search"}).json()
        with connect() as conn:
            payload = __import__("json").loads(conn.execute("SELECT payload FROM lessons WHERE id=?", ("linear-search",)).fetchone()["payload"])
        questions = payload["questions"]["checkpoint"]
        wrong = next(option for option in questions[0]["options"] if option != questions[0]["answer"])
        first = client.post(f"/api/sessions/{session['session_id']}/answers", headers=auth(session), json={"question_id": questions[0]["id"], "phase": "checkpoint", "concept": "linear-search", "answer": wrong}).json()
        assert first["incorrect_streak"] == 1
        second = client.post(f"/api/sessions/{session['session_id']}/answers", headers=auth(session), json={"question_id": questions[1]["id"], "phase": "checkpoint", "concept": "linear-search", "answer": questions[1]["answer"]}).json()
        assert second["incorrect_streak"] == 0
        third = client.post(f"/api/sessions/{session['session_id']}/answers", headers=auth(session), json={"question_id": questions[2]["id"], "phase": "checkpoint", "concept": "linear-search", "answer": next(option for option in questions[2]["options"] if option != questions[2]["answer"])}).json()
        assert third["incorrect_streak"] == 1


def test_personalized_history_uses_completed_followups_only():
    with ResearchClient(app) as client:
        lesson = client.get("/api/lessons").json()[1]
        with connect() as conn:
            import json
            payload = json.loads(conn.execute("SELECT payload FROM lessons WHERE id=?", ("binary-search",)).fetchone()["payload"])
        followups = payload["questions"]["follow_up"][:2]
        participant_code = "history-" + uuid.uuid4().hex[:8]
        first = client.post("/api/sessions", json={"participant_code": participant_code, "mode": "personalized", "lesson_id": "binary-search"}).json()
        event = {"client_event_id": "history-event-1", "event_type": "help_requested", "payload": {"interaction": {"concept": "binary-search", "help_requested": True}, "signal_summary": {}}}
        state = client.post(f"/api/sessions/{first['session_id']}/events", headers=auth(first), json=event).json()["state"]
        intervention_id = state["intervention"]["id"]
        client.post(f"/api/sessions/{first['session_id']}/interventions/{intervention_id}/response", headers=auth(first), json={"action": "accept"})
        for question in followups:
            client.post(f"/api/sessions/{first['session_id']}/interventions/{intervention_id}/follow-ups", headers=auth(first), json={"question_id": question["id"], "answer": question["answer"]})
        with connect() as conn:
            aggregate = conn.execute("SELECT a.completed_interventions, a.outcome_sum FROM personalization_aggregates a JOIN participants p ON p.id=a.participant_id WHERE p.code=? AND a.concept=? AND a.kind='simplified'", (participant_code, "binary-search")).fetchone()
            assert aggregate["completed_interventions"] == 1 and aggregate["outcome_sum"] == 1.0
        second = client.post("/api/sessions", json={"participant_code": participant_code, "mode": "personalized", "lesson_id": "binary-search"}).json()
        event["client_event_id"] = "history-event-2"
        state2 = client.post(f"/api/sessions/{second['session_id']}/events", headers=auth(second), json=event).json()["state"]
        assert state2["intervention"]["kind"] == "worked_example"
        assert state2["intervention"]["selection_reason"] == "exploration of an unused support type"
        assert state2["intervention"]["follow_up_bank"] == "follow_up_repeat"
        repeat_id = state2["intervention"]["id"]
        client.post(f"/api/sessions/{second['session_id']}/interventions/{repeat_id}/response", headers=auth(second), json={"action": "accept"})
        repeat_followups = payload["questions"]["follow_up_repeat"]
        for question in repeat_followups:
            response = client.post(f"/api/sessions/{second['session_id']}/interventions/{repeat_id}/follow-ups", headers=auth(second), json={"question_id": question["id"], "answer": question["answer"]})
            assert response.status_code == 200 and response.json()["correct"] is True


def test_intervention_view_dismiss_skip_are_idempotent():
    with ResearchClient(app) as client:
        session = client.post("/api/sessions", json={"participant_code": "lifecycle-" + uuid.uuid4().hex[:8], "mode": "rule_based", "lesson_id": "bubble-sort"}).json()
        payload = {"client_event_id": "lifecycle-event", "event_type": "help_requested", "payload": {"interaction": {"concept": "bubble-sort", "help_requested": True}, "signal_summary": {}}}
        state = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json=payload).json()["state"]
        intervention_id = state["intervention"]["id"]
        viewed = client.post(f"/api/sessions/{session['session_id']}/interventions/{intervention_id}/response", headers=auth(session), json={"action": "view"})
        assert viewed.json()["status"] == "viewed"
        skipped = client.post(f"/api/sessions/{session['session_id']}/interventions/{intervention_id}/response", headers=auth(session), json={"action": "skip"})
        assert skipped.json()["status"] == "skipped"
        duplicate = client.post(f"/api/sessions/{session['session_id']}/interventions/{intervention_id}/response", headers=auth(session), json={"action": "skip"})
        assert duplicate.json()["deduplicated"] is True


def test_late_view_does_not_revert_accepted_support_or_block_followups():
    with ResearchClient(app) as client:
        session = client.post(
            "/api/sessions",
            json={
                "participant_code": "accept-view-" + uuid.uuid4().hex[:8],
                "mode": "rule_based",
                "lesson_id": "binary-search",
            },
        ).json()
        event = {
            "client_event_id": "accept-view-event",
            "event_type": "help_requested",
            "payload": {"interaction": {"concept": "binary-search", "help_requested": True}},
        }
        state = client.post(
            f"/api/sessions/{session['session_id']}/events",
            headers=auth(session),
            json=event,
        ).json()["state"]
        intervention_id = state["intervention"]["id"]
        response_url = f"/api/sessions/{session['session_id']}/interventions/{intervention_id}/response"
        accepted = client.post(response_url, headers=auth(session), json={"action": "accept"})
        assert accepted.json()["status"] == "accepted"
        late_view = client.post(response_url, headers=auth(session), json={"action": "view"})
        assert late_view.json()["status"] == "accepted"
        lesson = next(item for item in client.get("/api/lessons").json() if item["id"] == "binary-search")
        question = lesson["questions"]["follow_up"][0]
        follow_up = client.post(
            f"/api/sessions/{session['session_id']}/interventions/{intervention_id}/follow-ups",
            headers=auth(session),
            json={"question_id": question["id"], "answer": question["options"][0]},
        )
        assert follow_up.status_code == 200


def test_exports_include_provenance_and_no_raw_camera_material():
    with ResearchClient(app) as client:
        session = client.post("/api/sessions", json={"participant_code": "export-" + uuid.uuid4().hex[:8], "mode": "static", "lesson_id": "linear-search", "study_kind": "study", "camera_consent": True}).json()
        signal_response = client.post(
            f"/api/sessions/{session['session_id']}/events",
            headers=auth(session),
            json={
                "client_event_id": "behavior-summary",
                "event_type": "signal_summary",
                "payload": {
                    "signal_summary": {
                        "enabled": True,
                        "face_present": True,
                        "blink_count": 3,
                        "gaze_direction": "LEFT",
                        "head_yaw_degrees": 12.5,
                        "head_pitch_degrees": -3.0,
                        "head_roll_degrees": 1.25,
                        "landmarks": "must not be included",
                    }
                },
            },
        )
        assert signal_response.status_code == 422
        signal_payload = {
            "client_event_id": "behavior-summary",
            "event_type": "signal_summary",
            "payload": {
                "signal_summary": {
                    "enabled": True,
                    "face_present": True,
                    "blink_count": 3,
                    "gaze_direction": "LEFT",
                    "head_yaw_degrees": 12.5,
                    "head_pitch_degrees": -3.0,
                    "head_roll_degrees": 1.25,
                    "landmarks": "stripped by allowlist",
                    "unrecognized_debug_value": "discard me",
                }
            },
        }
        signal_payload["payload"]["signal_summary"].pop("landmarks")
        accepted_signal = client.post(
            f"/api/sessions/{session['session_id']}/events",
            headers=auth(session),
            json=signal_payload,
        )
        assert accepted_signal.status_code == 200
        question = client.get("/api/lessons").json()[2]["questions"]["pre"][0]
        client.post(f"/api/sessions/{session['session_id']}/answers", headers=auth(session), json={"question_id": question["id"], "phase": "pre", "concept": question["concept"], "answer": question["options"][0], "response_time_ms": 800})
        feedback = client.post(f"/api/sessions/{session['session_id']}/feedback", headers=auth(session), json={"usability_rating": 4, "ease_rating": 5, "comment": "Clear enough"})
        assert feedback.status_code == 200 and feedback.json()["deduplicated"] is False
        duplicate_feedback = client.post(f"/api/sessions/{session['session_id']}/feedback", headers=auth(session), json={"usability_rating": 1})
        assert duplicate_feedback.status_code == 200 and duplicate_feedback.json()["deduplicated"] is True
        export = client.get(f"/api/sessions/{session['session_id']}/export.csv", headers=auth(session))
        assert export.status_code == 200
        assert "participant_code" in export.text and "content_version" in export.text and "completeness" in export.text and "feedback_usability_rating" in export.text and "feedback" in export.text
        assert "landmarks" not in export.text and "image_data" not in export.text
        study = client.get("/api/research/export.csv", headers={"X-Researcher-Token": "local-researcher"})
        assert study.status_code == 200 and "helpfulness" in study.text
        import csv, io
        session_rows = list(csv.reader(io.StringIO(export.text)))
        study_rows = list(csv.reader(io.StringIO(study.text)))
        assert all(len(row) == len(session_rows[0]) for row in session_rows)
        assert all(len(row) == len(study_rows[0]) for row in study_rows)
        assert "active_time_ms" in session_rows[0] and "signal_face_present" in session_rows[0]
        for field in (
            "signal_gaze_direction",
            "signal_head_yaw_degrees",
            "signal_head_pitch_degrees",
            "signal_head_roll_degrees",
        ):
            assert field in session_rows[0] and field in study_rows[0]
        signal_row = next(row for row in session_rows[1:] if row[0] == "signal_summary")
        signal_values = dict(zip(session_rows[0], signal_row))
        assert signal_values["signal_gaze_direction"] == "LEFT"
        assert signal_values["signal_head_yaw_degrees"] == "12.5"
        study_signal_row = next(
            row
            for row in study_rows[1:]
            if row[1] == session["participant_code"] and row[11] == "signal_summary"
        )
        study_signal_values = dict(zip(study_rows[0], study_signal_row))
        assert study_signal_values["signal_gaze_direction"] == "LEFT"
        assert study_signal_values["signal_head_roll_degrees"] == "1.25"
        detail = client.get(f"/api/sessions/{session['session_id']}", headers=auth(session)).json()
        assert detail["feedback"]["usability_rating"] == 4
        stored_signal = next(
            event["payload"]["signal_summary"]
            for event in detail["events"]
            if event["event_type"] == "signal_summary"
        )
        assert stored_signal["gaze_direction"] == "LEFT"
        assert stored_signal["head_yaw_degrees"] == 12.5
        assert "unrecognized_debug_value" not in stored_signal


def test_research_assignments_require_researcher_access_and_return_versioned_rotation():
    with ResearchClient(app) as client:
        denied = client.get("/api/research/assignments")
        assert denied.status_code == 401
        response = client.get("/api/research/assignments", headers={"X-Researcher-Token": "local-researcher"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["content_version"] == "v2"
        assert payload["policy_version"] == "v2"
        assert len(payload["assignments"]) == 3
        assert all(set(row) == {"participant_code", "session_1", "session_2", "session_3"} for row in payload["assignments"])


def test_all_lesson_mode_combinations_start_and_grade():
    with ResearchClient(app) as client:
        lessons = client.get("/api/lessons").json()
        for lesson in lessons:
            for mode in ("static", "rule_based", "personalized"):
                session = client.post("/api/sessions", json={"participant_code": f"matrix-{uuid.uuid4().hex[:8]}", "mode": mode, "lesson_id": lesson["id"]}).json()
                question = lesson["questions"]["pre"][0]
                answer = client.post(f"/api/sessions/{session['session_id']}/answers", headers=auth(session), json={"question_id": question["id"], "phase": "pre", "concept": question["concept"], "answer": question["options"][0], "response_time_ms": 500})
                assert answer.status_code == 200
                event = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json={"client_event_id": uuid.uuid4().hex, "event_type": "signal_summary", "payload": {"interaction": {"concept": lesson["id"], "incorrect_streak": 0}, "signal_summary": {"face_present": None}}})
                assert event.status_code == 200 and event.json()["state"]["intervention"] is None


def test_raw_camera_material_is_rejected_from_event_ingest():
    with ResearchClient(app) as client:
        session = client.post("/api/sessions", json={"participant_code": "privacy-" + uuid.uuid4().hex[:8], "mode": "static", "lesson_id": "linear-search"}).json()
        response = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json={"client_event_id": "raw-camera", "event_type": "signal_summary", "payload": {"signal_summary": {"face_present": True, "landmarks": [{"x": 0.1}]}}})
        assert response.status_code == 422


def test_behavior_indicators_remain_observational_only():
    with ResearchClient(app) as client:
        session = client.post(
            "/api/sessions",
            json={
                "participant_code": "behavior-neutral-" + uuid.uuid4().hex[:8],
                "mode": "personalized",
                "lesson_id": "linear-search",
            },
        ).json()
        response = client.post(
            f"/api/sessions/{session['session_id']}/events",
            headers=auth(session),
            json={
                "client_event_id": "behavior-observation",
                "event_type": "signal_summary",
                "payload": {
                    "signal_summary": {
                        "enabled": True,
                        "face_present": True,
                        "blink_count": 8,
                        "gaze_direction": "LEFT",
                        "head_yaw_degrees": 35.0,
                        "head_pitch_degrees": 2.0,
                        "head_roll_degrees": -1.0,
                    }
                },
            },
        )
        assert response.status_code == 200
        assert response.json()["state"]["intervention"] is None
        assert response.json()["state"]["observations"] == []


def test_health_endpoints_report_live_and_ready():
    with ResearchClient(app) as client:
        assert client.get("/health/live").json()["status"] == "ok"
        assert client.get("/health/ready").json()["status"] == "ready"


def test_assessment_and_followup_retries_return_canonical_saved_result():
    with ResearchClient(app) as client:
        lesson = next(item for item in client.get("/api/lessons").json() if item["id"] == "binary-search")
        question = lesson["questions"]["pre"][0]
        session = client.post("/api/sessions", json={"participant_code": "retry-" + uuid.uuid4().hex[:8], "mode": "rule_based", "lesson_id": "binary-search"}).json()
        answer_body = {"question_id": question["id"], "phase": "pre", "concept": question["concept"], "answer": question["options"][0]}
        first = client.post(f"/api/sessions/{session['session_id']}/answers", headers=auth(session), json=answer_body)
        assert first.json()["correct"] is True
        altered = {**answer_body, "answer": question["options"][1]}
        retry = client.post(f"/api/sessions/{session['session_id']}/answers", headers=auth(session), json=altered)
        assert retry.json()["deduplicated"] is True and retry.json()["correct"] is True

        event = {"client_event_id": "retry-support", "event_type": "help_requested", "payload": {"interaction": {"concept": "binary-search", "help_requested": True}}}
        state = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json=event).json()["state"]
        intervention_id = state["intervention"]["id"]
        follow = lesson["questions"]["follow_up"][0]
        with connect() as conn:
            import json
            stored_lesson = json.loads(conn.execute("SELECT payload FROM lessons WHERE id=?", ("binary-search",)).fetchone()["payload"])
        follow_key = next(item for item in stored_lesson["questions"]["follow_up"] if item["id"] == follow["id"])["answer"]
        before_accept = client.post(f"/api/sessions/{session['session_id']}/interventions/{intervention_id}/follow-ups", headers=auth(session), json={"question_id": follow["id"], "answer": follow_key})
        assert before_accept.status_code == 409
        client.post(f"/api/sessions/{session['session_id']}/interventions/{intervention_id}/response", headers=auth(session), json={"action": "accept"})
        first_follow = client.post(f"/api/sessions/{session['session_id']}/interventions/{intervention_id}/follow-ups", headers=auth(session), json={"question_id": follow["id"], "answer": follow_key})
        assert first_follow.json()["correct"] is True
        altered_follow = client.post(f"/api/sessions/{session['session_id']}/interventions/{intervention_id}/follow-ups", headers=auth(session), json={"question_id": follow["id"], "answer": next(option for option in follow["options"] if option != follow_key)})
        assert altered_follow.json()["deduplicated"] is True and altered_follow.json()["correct"] is True


def test_terminal_intervention_cannot_be_reopened_by_late_view():
    with ResearchClient(app) as client:
        session = client.post("/api/sessions", json={"participant_code": "terminal-" + uuid.uuid4().hex[:8], "mode": "rule_based", "lesson_id": "linear-search"}).json()
        event = {"client_event_id": "terminal-support", "event_type": "help_requested", "payload": {"interaction": {"concept": "linear-search", "help_requested": True}}}
        state = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json=event).json()["state"]
        intervention_id = state["intervention"]["id"]
        client.post(f"/api/sessions/{session['session_id']}/interventions/{intervention_id}/response", headers=auth(session), json={"action": "dismiss"})
        late_view = client.post(f"/api/sessions/{session['session_id']}/interventions/{intervention_id}/response", headers=auth(session), json={"action": "view"})
        assert late_view.json() == {"saved": True, "status": "dismissed", "deduplicated": True}


def test_automatic_cooldown_does_not_block_explicit_help():
    with ResearchClient(app) as client:
        session = client.post("/api/sessions", json={"participant_code": "cooldown-" + uuid.uuid4().hex[:8], "mode": "rule_based", "lesson_id": "bubble-sort"}).json()
        submit_wrong_checkpoints(client, session)
        first_event = {"client_event_id": "cooldown-first", "event_type": "difficulty_detected", "payload": {"interaction": {"concept": "bubble-sort", "incorrect_streak": 2, "quiz_correct": False}}}
        first = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json=first_event).json()["state"]
        intervention_id = first["intervention"]["id"]
        client.post(f"/api/sessions/{session['session_id']}/interventions/{intervention_id}/response", headers=auth(session), json={"action": "skip"})
        automatic = {"client_event_id": "cooldown-second", "event_type": "difficulty_detected", "payload": {"interaction": {"concept": "bubble-sort", "incorrect_streak": 2, "quiz_correct": False}}}
        automatic_state = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json=automatic).json()["state"]
        assert automatic_state["intervention"] is None and any("cooldown" in reason.lower() for reason in automatic_state["reasons"])
        explicit = {"client_event_id": "cooldown-help", "event_type": "help_requested", "payload": {"interaction": {"concept": "bubble-sort", "help_requested": True}}}
        explicit_state = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json=explicit).json()["state"]
        assert explicit_state["intervention"] is not None


def test_camera_context_only_reports_observation_and_unavailable_stays_neutral():
    with ResearchClient(app) as client:
        session = client.post("/api/sessions", json={"participant_code": "camera-context-" + uuid.uuid4().hex[:8], "mode": "personalized", "lesson_id": "linear-search", "camera_consent": True}).json()
        sustained = {"client_event_id": "camera-context", "event_type": "signal_summary", "payload": {"interaction": {"concept": "linear-search", "incorrect_streak": 0}, "signal_summary": {"enabled": True, "face_present": False, "looking_away": True, "ambiguous": True, "sustained_seconds": 30}}}
        state = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json=sustained).json()["state"]
        assert state["intervention"] is None
        assert len(state["observations"]) == 2
        saved = client.get(f"/api/sessions/{session['session_id']}", headers=auth(session)).json()
        assert saved["events"][0]["payload"]["signal_summary"]["ambiguous"] is True
        unavailable = {"client_event_id": "camera-unavailable", "event_type": "signal_summary", "payload": {"interaction": {"concept": "linear-search", "incorrect_streak": 0}, "signal_summary": {"enabled": False, "face_present": None, "looking_away": None, "blink_count": None, "status": "Camera unavailable"}}}
        neutral = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json=unavailable).json()["state"]
        assert neutral["intervention"] is None and neutral["observations"] == []


def test_incorrect_long_response_triggers_support_without_a_two_error_streak():
    with ResearchClient(app) as client:
        session = client.post("/api/sessions", json={"participant_code": "long-response-" + uuid.uuid4().hex[:8], "mode": "rule_based", "lesson_id": "linear-search"}).json()
        submit_wrong_checkpoints(client, session, 1, 45001)
        event = {
            "client_event_id": "long-response",
            "event_type": "difficulty_detected",
            "payload": {"interaction": {"concept": "linear-search", "incorrect_streak": 1, "quiz_correct": False, "response_time_ms": 45001, "revisits": 0}},
        }
        state = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json=event).json()["state"]
        assert state["intervention"] is not None
        assert any("long response" in reason for reason in state["reasons"])


def test_progress_validates_lesson_membership_and_completed_sessions_reject_late_mutations():
    with ResearchClient(app) as client:
        session = client.post("/api/sessions", json={"participant_code": "progress-boundary-" + uuid.uuid4().hex[:8], "mode": "rule_based", "lesson_id": "linear-search"}).json()
        sid = session["session_id"]
        invalid_section = client.post(f"/api/sessions/{sid}/progress", headers=auth(session), json={"phase": "learn", "section_id": "not-a-section", "active_time_ms": 0, "elapsed_time_ms": 0})
        assert invalid_section.status_code == 422
        invalid_question = client.post(f"/api/sessions/{sid}/progress", headers=auth(session), json={"phase": "pre", "question_id": "bs-pre-1", "section_id": "explain", "active_time_ms": 0, "elapsed_time_ms": 0})
        assert invalid_question.status_code == 422
        saved_progress = client.post(f"/api/sessions/{sid}/progress", headers=auth(session), json={"phase": "learn", "section_id": "explain", "section_visits": {"explain": 2, "example": 1}, "active_time_ms": 1200, "elapsed_time_ms": 2400})
        assert saved_progress.status_code == 200
        assert saved_progress.json()["progress"]["section_visits"] == {"explain": 2, "example": 1}
        resumed = client.get(f"/api/sessions/{sid}/resume", headers=auth(session)).json()
        assert resumed["progress"]["section_visits"] == {"explain": 2, "example": 1}
        assert client.post(f"/api/sessions/{sid}/end", headers=auth(session)).status_code == 200
        late_progress = client.post(f"/api/sessions/{sid}/progress", headers=auth(session), json={"phase": "done", "section_id": "explain", "active_time_ms": 0, "elapsed_time_ms": 0})
        assert late_progress.status_code == 409
        late_event = client.post(f"/api/sessions/{sid}/events", headers=auth(session), json={"client_event_id": "late", "event_type": "help_requested", "payload": {"interaction": {"help_requested": True}}})
        assert late_event.status_code == 409


def test_response_time_is_measured_from_presentation_timestamp_when_available():
    from datetime import datetime, timedelta, timezone
    with ResearchClient(app) as client:
        session = client.post("/api/sessions", json={"participant_code": "timing-" + uuid.uuid4().hex[:8], "mode": "static", "lesson_id": "linear-search"}).json()
        question = next(item for item in client.get("/api/lessons").json() if item["id"] == "linear-search")["questions"]["pre"][0]
        started = (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat()
        response = client.post(f"/api/sessions/{session['session_id']}/answers", headers=auth(session), json={"question_id": question["id"], "phase": "pre", "concept": question["concept"], "answer": question["options"][0], "response_time_ms": 1, "response_started_at": started})
        assert response.status_code == 200
        assert response.json()["response_time_ms"] >= 1500
        detail = client.get(f"/api/sessions/{session['session_id']}", headers=auth(session)).json()
        assert detail["answers"][0]["response_time_ms"] >= 1500


def test_multiple_support_requests_return_one_active_intervention():
    with ResearchClient(app) as client:
        session = client.post("/api/sessions", json={"participant_code": "one-active-" + uuid.uuid4().hex[:8], "mode": "rule_based", "lesson_id": "linear-search"}).json()
        first = {"client_event_id": "one-active-first", "event_type": "help_requested", "payload": {"interaction": {"concept": "linear-search", "help_requested": True}}}
        second = {"client_event_id": "one-active-second", "event_type": "difficulty_detected", "payload": {"interaction": {"concept": "linear-search", "incorrect_streak": 2, "quiz_correct": False}}}
        first_state = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json=first).json()["state"]
        second_state = client.post(f"/api/sessions/{session['session_id']}/events", headers=auth(session), json=second).json()["state"]
        assert first_state["intervention"]["id"] == second_state["intervention"]["id"]
        with connect() as conn:
            assert conn.execute("SELECT COUNT(*) AS count FROM interventions WHERE session_id=?", (session["session_id"],)).fetchone()["count"] == 1
