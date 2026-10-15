"""Run separately with IDP_DATABASE_URL and IDP_RESEARCHER_TOKEN set.

CI supplies a disposable PostgreSQL service. The test deliberately exercises
the release command and simultaneous requests against the same session.
"""

import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

if not (os.getenv("IDP_DATABASE_URL") or os.getenv("DATABASE_URL")):
    pytest.skip("PostgreSQL URL not configured", allow_module_level=True)

from backend.app.db import connect, init_db
from backend.app.main import app


def test_clean_prepare_concurrent_help_and_completed_aggregate():
    init_db()
    init_db()  # release preparation must be repeatable
    with connect() as conn:
        assert conn.execute("SELECT COUNT(*) AS count FROM schema_migrations").fetchone()["count"] == 9
        assert conn.execute("SELECT COUNT(*) AS count FROM lessons").fetchone()["count"] == 3
        lesson = json.loads(conn.execute("SELECT payload FROM lessons WHERE id='binary-search'").fetchone()["payload"])

    with TestClient(app) as client:
        response = client.post("/api/sessions", headers={"X-Researcher-Token": os.environ["IDP_RESEARCHER_TOKEN"]}, json={
            "participant_code": "pg-test-" + uuid.uuid4().hex[:16],
            "mode": "personalized", "lesson_id": "binary-search", "study_kind": "practice",
        })
        assert response.status_code == 200, response.text
        session = response.json()
        sid = session["session_id"]
        headers = {"X-Session-Token": session["access_token"]}

        def request_help(index):
            return client.post(f"/api/sessions/{sid}/events", headers=headers, json={
                "client_event_id": f"parallel-{index}", "event_type": "help_requested",
                "payload": {"interaction": {"concept": "binary-search", "help_requested": True}},
            })

        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(request_help, (1, 2)))
        assert all(item.status_code == 200 for item in responses), [item.text for item in responses]
        detail = client.get(f"/api/sessions/{sid}", headers=headers).json()
        assert len(detail["interventions"]) == 1
        intervention = detail["interventions"][0]
        assert intervention["kind"] == "simplified"

        accepted = client.post(f"/api/sessions/{sid}/interventions/{intervention['id']}/response", headers=headers, json={"action": "accept"})
        assert accepted.status_code == 200
        followups = lesson["questions"][intervention["follow_up_bank"]]
        for question in followups:
            response = client.post(f"/api/sessions/{sid}/interventions/{intervention['id']}/follow-ups", headers=headers, json={"question_id": question["id"], "answer": question["answer"]})
            assert response.status_code == 200, response.text
        history = client.get(f"/api/sessions/{sid}/support-history", headers=headers)
        assert history.status_code == 200
        assert any(row["kind"] == "simplified" and row["completed_interventions"] == 1 and row["outcome_sum"] == 1 for row in history.json())

    # A fresh API client must observe committed answers and support history.
    with TestClient(app) as client:
        detail = client.get(f"/api/sessions/{sid}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["interventions"][0]["status"] == "completed"
