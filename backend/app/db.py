"""Small SQLite persistence layer for the local academic prototype.

The schema is intentionally portable: all tables and values use standard SQL
types so the same model can be moved to PostgreSQL with a thin adapter later.
"""

from __future__ import annotations

import json
import os
import sqlite3
import re
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
DB_PATH = Path(os.getenv("IDP_DB_PATH", ROOT / "data" / "idp.sqlite3"))
DATABASE_URL = (os.getenv("IDP_DATABASE_URL") or os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or "").strip()
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)


class _SqlAlchemyResult:
    def __init__(self, result):
        self._result = result.mappings()
        self.rowcount = result.rowcount

    def fetchone(self):
        return self._result.fetchone()

    def fetchall(self):
        return self._result.fetchall()


class _PostgresConnection:
    """Small qmark-compatible adapter so the existing SQL stays portable."""
    def __init__(self):
        from sqlalchemy import create_engine
        global _ENGINE
        if _ENGINE is None:
            _ENGINE = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=2, max_overflow=1)
        self._connection = _ENGINE.connect()
        self._transaction = self._connection.begin()

    @staticmethod
    def _bind(sql: str, params: tuple[Any, ...] | list[Any] | None):
        values = tuple(params or ())
        if not values:
            return sql, {}
        index = 0
        def replace(_match):
            nonlocal index
            name = f"p{index}"; index += 1
            return f":{name}"
        return re.sub(r"\?", replace, sql), {f"p{i}": value for i, value in enumerate(values)}

    def execute(self, sql: str, params=()):
        from sqlalchemy import text
        bound, values = self._bind(sql, params)
        return _SqlAlchemyResult(self._connection.execute(text(bound), values))

    def lock_session(self, session_id: str):
        self.execute("SELECT id FROM sessions WHERE id=? FOR UPDATE", (session_id,)).fetchone()

    def executescript(self, script: str):
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self.execute(statement)

    def __enter__(self): return self
    def __exit__(self, exc_type, exc, tb):
        if exc_type: self._transaction.rollback()
        else: self._transaction.commit()
        self._connection.close()


_ENGINE = None


def connect():
    if DATABASE_URL:
        return _PostgresConnection()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("BEGIN IMMEDIATE")
    return conn


def init_db() -> None:
    with connect() as conn:
        if DATABASE_URL:
            conn.execute("SELECT pg_advisory_xact_lock(76321849)")
        schema = """
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                reset_group TEXT NOT NULL DEFAULT 'default',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS lessons (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                participant_id INTEGER NOT NULL REFERENCES participants(id),
                mode TEXT NOT NULL CHECK (mode IN ('static', 'rule_based', 'personalized')),
                lesson_id TEXT NOT NULL REFERENCES lessons(id),
                access_token TEXT NOT NULL DEFAULT '',
                study_kind TEXT NOT NULL DEFAULT 'practice',
                camera_consent INTEGER NOT NULL DEFAULT 0,
                data_origin TEXT NOT NULL DEFAULT 'observed',
                content_version TEXT NOT NULL DEFAULT 'v1',
                policy_version TEXT NOT NULL DEFAULT 'v1',
                reset_group TEXT NOT NULL DEFAULT 'default',
                progress_phase TEXT NOT NULL DEFAULT 'pre',
                progress_question_id TEXT,
                progress_question_index INTEGER NOT NULL DEFAULT 0,
                progress_section_id TEXT NOT NULL DEFAULT 'explain',
                section_visits TEXT NOT NULL DEFAULT '{}',
                active_time_ms INTEGER NOT NULL DEFAULT 0,
                elapsed_time_ms INTEGER NOT NULL DEFAULT 0,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ended_at TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                client_event_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                decision_json TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, client_event_id)
            );
            CREATE TABLE IF NOT EXISTS answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                question_id TEXT NOT NULL,
                phase TEXT NOT NULL,
                concept TEXT NOT NULL,
                answer TEXT NOT NULL,
                correct INTEGER NOT NULL,
                response_time_ms INTEGER,
                response_started_at TEXT,
                submitted_at TEXT,
                section_id TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, question_id, phase)
            );
            CREATE TABLE IF NOT EXISTS interventions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL REFERENCES sessions(id),
                concept TEXT NOT NULL,
                kind TEXT NOT NULL,
                trigger TEXT NOT NULL,
                reason TEXT NOT NULL,
                selection_reason TEXT NOT NULL DEFAULT '',
                follow_up_bank TEXT NOT NULL DEFAULT 'follow_up',
                status TEXT NOT NULL DEFAULT 'offered',
                accepted INTEGER,
                viewed_at TEXT,
                skipped_at TEXT,
                completed_at TEXT,
                dismissed_at TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS follow_ups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                intervention_id INTEGER NOT NULL REFERENCES interventions(id),
                question_id TEXT NOT NULL,
                answer TEXT,
                correct INTEGER NOT NULL,
                helpfulness INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(intervention_id, question_id)
            );
            CREATE TABLE IF NOT EXISTS personalization_aggregates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                participant_id INTEGER NOT NULL REFERENCES participants(id),
                reset_group TEXT NOT NULL DEFAULT 'default',
                mode TEXT NOT NULL,
                concept TEXT NOT NULL,
                kind TEXT NOT NULL,
                completed_interventions INTEGER NOT NULL DEFAULT 0,
                outcome_sum REAL NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(participant_id, reset_group, mode, concept, kind)
            );
            CREATE TABLE IF NOT EXISTS session_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL UNIQUE REFERENCES sessions(id),
                support_helpfulness INTEGER,
                usability_rating INTEGER,
                ease_rating INTEGER,
                comment TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        if DATABASE_URL:
            schema = schema.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
        conn.executescript(schema)
        add_missing_columns(conn)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_intervention ON interventions(session_id) WHERE status IN ('offered', 'viewed', 'accepted')")
        if DATABASE_URL:
            apply_versioned_migrations(conn)
        seed_lessons(conn)
        backfill_personalization_aggregates(conn)


def apply_versioned_migrations(conn) -> None:
    """Apply and record the checked-in PostgreSQL migration files."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    migration_dir = BACKEND_ROOT / "migrations"
    for path in sorted(migration_dir.glob("*.sql")):
        version = path.stem
        if conn.execute("SELECT 1 FROM schema_migrations WHERE version=?", (version,)).fetchone():
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))


def backfill_personalization_aggregates(conn) -> None:
    """Rebuild the derived personalization table from completed support rows."""
    conn.execute("DELETE FROM personalization_aggregates")
    rows = conn.execute("""
        SELECT s.participant_id, s.reset_group, s.mode, i.concept, i.kind,
               COUNT(DISTINCT i.id) AS completed_interventions,
               COALESCE(SUM(f.correct), 0) / 2.0 AS outcome_sum
        FROM interventions i
        JOIN sessions s ON s.id=i.session_id
        JOIN follow_ups f ON f.intervention_id=i.id
        WHERE i.status='completed'
        GROUP BY s.participant_id, s.reset_group, s.mode, i.concept, i.kind
    """).fetchall()
    for row in rows:
        conn.execute(
            "INSERT INTO personalization_aggregates (participant_id, reset_group, mode, concept, kind, completed_interventions, outcome_sum) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (row["participant_id"], row["reset_group"], row["mode"], row["concept"], row["kind"], row["completed_interventions"], row["outcome_sum"]),
        )


def _table_columns(conn, table: str) -> set[str]:
    if DATABASE_URL:
        rows = conn.execute("SELECT column_name AS name FROM information_schema.columns WHERE table_name=?", (table,)).fetchall()
        return {row["name"] for row in rows}
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def add_missing_columns(conn) -> None:
    """Apply additive migrations to the original SQLite prototype database."""
    existing = _table_columns(conn, "sessions")
    participant_columns = _table_columns(conn, "participants")
    if "reset_group" not in participant_columns:
        conn.execute("ALTER TABLE participants ADD COLUMN reset_group TEXT NOT NULL DEFAULT 'default'")
    additions = {
        "software_revision": "TEXT NOT NULL DEFAULT 'unknown'",
        "policy_config": "TEXT NOT NULL DEFAULT '{}'",
        "access_token": "TEXT NOT NULL DEFAULT ''",
        "study_kind": "TEXT NOT NULL DEFAULT 'practice'",
        "camera_consent": "INTEGER NOT NULL DEFAULT 0",
        "data_origin": "TEXT NOT NULL DEFAULT 'observed'",
        "content_version": "TEXT NOT NULL DEFAULT 'v1'",
        "policy_version": "TEXT NOT NULL DEFAULT 'v1'",
        "reset_group": "TEXT NOT NULL DEFAULT 'default'",
        "progress_phase": "TEXT NOT NULL DEFAULT 'pre'",
        "progress_question_id": "TEXT",
        "progress_question_index": "INTEGER NOT NULL DEFAULT 0",
        "progress_section_id": "TEXT NOT NULL DEFAULT 'explain'",
        "section_visits": "TEXT NOT NULL DEFAULT '{}'",
        "active_time_ms": "INTEGER NOT NULL DEFAULT 0",
        "elapsed_time_ms": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, definition in additions.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE sessions ADD COLUMN {name} {definition}")
    table_columns = {
        "events": _table_columns(conn, "events"),
        "answers": _table_columns(conn, "answers"),
        "interventions": _table_columns(conn, "interventions"),
        "follow_ups": _table_columns(conn, "follow_ups"),
    }
    feedback_columns = _table_columns(conn, "session_feedback")
    if "support_helpfulness" not in feedback_columns:
        conn.execute("ALTER TABLE session_feedback ADD COLUMN support_helpfulness INTEGER")
    for name, definition in {"decision_json": "TEXT"}.items():
        if name not in table_columns["events"]:
            conn.execute(f"ALTER TABLE events ADD COLUMN {name} {definition}")
    for name, definition in {"response_started_at": "TEXT", "submitted_at": "TEXT", "section_id": "TEXT"}.items():
        if name not in table_columns["answers"]:
            conn.execute(f"ALTER TABLE answers ADD COLUMN {name} {definition}")
    for name, definition in {
        "selection_reason": "TEXT NOT NULL DEFAULT ''", "follow_up_bank": "TEXT NOT NULL DEFAULT 'follow_up'", "status": "TEXT NOT NULL DEFAULT 'offered'",
        "viewed_at": "TEXT", "skipped_at": "TEXT", "completed_at": "TEXT",
    }.items():
        if name not in table_columns["interventions"]:
            conn.execute(f"ALTER TABLE interventions ADD COLUMN {name} {definition}")
    if "answer" not in table_columns["follow_ups"]:
        conn.execute("ALTER TABLE follow_ups ADD COLUMN answer TEXT")
    # Existing prototype sessions used zero timings and fallback camera
    # values. Preserve them, but make their provenance explicit so reports do
    # not present them as verified observations.
    conn.execute("UPDATE sessions SET data_origin='legacy_unverified' WHERE content_version='v1' AND data_origin='observed'")


def seed_lessons(conn: sqlite3.Connection) -> None:
    lessons = [
        {
            "id": "linear-search",
            "title": "Linear Search",
            "summary": "Find an item by checking each value from left to right.",
            "objectives": ["Trace a linear search", "Explain when linear search is useful", "State its best and worst case work"],
            "prerequisites": ["Lists and indices"],
            "complexity": "Best case O(1); worst case O(n) time; O(1) extra space.",
            "sections": [
                {"id": "explain", "title": "How it works", "body": "Linear search checks the first item, then the next, until the target is found or the list ends.", "example": "For [4, 9, 2, 7], searching for 2 checks 4, then 9, then 2."},
                {"id": "simplify", "title": "A simpler explanation", "body": "Imagine looking for a name in an unsorted attendance sheet. You must read names one by one.", "example": "If the target is last, every item is checked."},
                {"id": "practice", "title": "Guided practice", "body": "Trace the checks aloud: compare the target with the current item, then move right.", "example": "Target 7 in [3, 5, 7] takes three comparisons."}
            ],
            "questions": {
                "pre": [{"id": "ls-pre-1", "concept": "linear-search", "prompt": "What does linear search do first?", "options": ["Check the first item", "Sort the list", "Jump to the middle"], "answer": "Check the first item"}],
                "checkpoint": [{"id": "ls-check-1", "concept": "linear-search", "prompt": "In [8, 3, 5], how many checks find 5?", "options": ["1", "2", "3"], "answer": "3"}, {"id": "ls-check-2", "concept": "linear-search", "prompt": "Does linear search require a sorted list?", "options": ["Yes", "No"], "answer": "No"}],
                "post": [{"id": "ls-post-1", "concept": "linear-search", "prompt": "What is the worst-case work for n items?", "options": ["One check", "n checks", "n² checks"], "answer": "n checks"}]
            }
        },
        {
            "id": "binary-search",
            "title": "Binary Search",
            "summary": "Narrow a sorted list by half after every comparison.",
            "objectives": ["Maintain low, middle, and high bounds", "Explain the sorted-input requirement", "Trace logarithmic search progress"],
            "prerequisites": ["Sorted lists and comparisons"],
            "complexity": "O(log n) time on a sorted list; O(1) extra space for the iterative version.",
            "sections": [
                {"id": "explain", "title": "How it works", "body": "Binary search requires sorted data. Compare the target with the middle item, then keep only the half that can contain it.", "example": "In [2, 4, 6, 8, 10], target 8: compare 6, then 8."},
                {"id": "simplify", "title": "A simpler explanation", "body": "Think of finding a word in a dictionary: open near the middle and discard the half that cannot contain the word.", "example": "Every comparison removes about half the remaining choices."},
                {"id": "practice", "title": "Guided practice", "body": "Mark low, middle, and high. After each comparison, move low or high inward.", "example": "For 1–16, four comparisons are enough to find any value."}
            ],
            "questions": {
                "pre": [{"id": "bs-pre-1", "concept": "binary-search", "prompt": "What must be true before binary search begins?", "options": ["The list is sorted", "The list has 100 items", "The target is first"], "answer": "The list is sorted"}],
                "checkpoint": [{"id": "bs-check-1", "concept": "binary-search", "prompt": "After checking the middle, what can you discard?", "options": ["Nothing", "The impossible half", "The whole list"], "answer": "The impossible half"}, {"id": "bs-check-2", "concept": "binary-search", "prompt": "What is the typical time complexity?", "options": ["O(log n)", "O(n)", "O(n²)"], "answer": "O(log n)"}],
                "post": [{"id": "bs-post-1", "concept": "binary-search", "prompt": "Why is binary search faster on a large sorted list?", "options": ["It checks every item", "It removes half the choices each step", "It sorts after every check"], "answer": "It removes half the choices each step"}]
            }
        },
        {
            "id": "bubble-sort",
            "title": "Bubble Sort",
            "summary": "Repeatedly swap adjacent values that are out of order.",
            "objectives": ["Trace adjacent swaps", "Explain why a pass moves a large value right", "Identify the early-stop condition"],
            "prerequisites": ["Lists, comparisons, and swaps"],
            "complexity": "O(n²) worst-case time; O(n) best case with an early-stop check; O(1) extra space.",
            "sections": [
                {"id": "explain", "title": "How it works", "body": "Bubble sort compares neighbors and swaps them when the left value is larger. Large values move toward the end after each pass.", "example": "[3, 1, 2] becomes [1, 2, 3] after repeated neighbor swaps."},
                {"id": "simplify", "title": "A simpler explanation", "body": "Walk along the list and fix every pair that is backwards. Repeat until a full pass makes no swaps.", "example": "A pass with no swaps means the list is sorted."},
                {"id": "practice", "title": "Guided practice", "body": "Circle each adjacent pair, decide whether to swap, and count the passes.", "example": "After one pass, the largest remaining value is at the right."}
            ],
            "questions": {
                "pre": [{"id": "bub-pre-1", "concept": "bubble-sort", "prompt": "Which values does bubble sort compare?", "options": ["Adjacent values", "Only the first and last", "Random values"], "answer": "Adjacent values"}],
                "checkpoint": [{"id": "bub-check-1", "concept": "bubble-sort", "prompt": "What happens when a neighbor pair is out of order?", "options": ["Swap them", "Delete them", "Stop immediately"], "answer": "Swap them"}, {"id": "bub-check-2", "concept": "bubble-sort", "prompt": "When can a pass finish the algorithm?", "options": ["When no swaps occur", "After one comparison", "When the first value is small"], "answer": "When no swaps occur"}],
                "post": [{"id": "bub-post-1", "concept": "bubble-sort", "prompt": "What moves toward the end after a complete pass?", "options": ["The largest remaining value", "The smallest value", "Nothing"], "answer": "The largest remaining value"}]
            }
        }
    ]
    for lesson in lessons:
        conn.execute(
            "INSERT INTO lessons (id, title, summary, payload) VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET title=excluded.title, summary=excluded.summary, payload=excluded.payload",
            (lesson["id"], lesson["title"], lesson["summary"], json.dumps(lesson)),
        )
    expand_question_bank(conn)


def expand_question_bank(conn: sqlite3.Connection) -> None:
    """Add the distinct pilot banks and visualizer metadata to every lesson."""
    extras = {
        "linear-search": {
            "pre": [
                {"id": "ls-pre-2", "concept": "linear-search", "prompt": "What happens when the target is not present?", "options": ["The scan reaches the end", "The list sorts itself", "The middle item is returned"], "answer": "The scan reaches the end"},
                {"id": "ls-pre-3", "concept": "linear-search", "prompt": "Which list can linear search handle?", "options": ["Only sorted lists", "Sorted or unsorted lists", "Only empty lists"], "answer": "Sorted or unsorted lists"},
            ],
            "checkpoint": [
                {"id": "ls-check-3", "concept": "linear-search", "prompt": "If the first value matches, how much work was needed?", "options": ["One comparison", "n comparisons", "A full sort"], "answer": "One comparison"},
                {"id": "ls-check-4", "concept": "linear-search", "prompt": "Which pointer moves during a left-to-right scan?", "options": ["The current index", "The list length", "The target value"], "answer": "The current index"},
                {"id": "ls-check-5", "concept": "linear-search", "prompt": "What is the worst case when the target is missing?", "options": ["Check every value", "Check only the middle", "No checks"], "answer": "Check every value"},
                {"id": "ls-check-6", "concept": "linear-search", "prompt": "What should a search return when no match exists?", "options": ["A not-found result", "The first value", "A random index"], "answer": "A not-found result"},
            ],
            "post": [
                {"id": "ls-post-2", "concept": "linear-search", "prompt": "Which input condition makes linear search especially simple?", "options": ["The target is first", "The list is sorted", "The list is encrypted"], "answer": "The target is first"},
                {"id": "ls-post-3", "concept": "linear-search", "prompt": "What does the index represent during the scan?", "options": ["The current value being checked", "The final list size", "The number of swaps"], "answer": "The current value being checked"},
            ],
            "follow_up": [
                {"id": "ls-follow-1", "concept": "linear-search", "prompt": "For [6, 1, 9], which index is checked first?", "options": ["0", "1", "2"], "answer": "0"},
                {"id": "ls-follow-2", "concept": "linear-search", "prompt": "If 4 is absent from [2, 5], what is the result?", "options": ["Not found", "Index 0", "Index 1"], "answer": "Not found"},
            ],
            "follow_up_repeat": [
                {"id": "ls-follow-repeat-1", "concept": "linear-search", "prompt": "In [7, 2, 9], which value is checked second?", "options": ["7", "2", "9"], "answer": "2"},
                {"id": "ls-follow-repeat-2", "concept": "linear-search", "prompt": "What should happen after the scan checks every value without a match?", "options": ["Report not found", "Jump to the middle", "Sort the list"], "answer": "Report not found"},
            ],
            "retention": [
                {"id": "ls-ret-1", "concept": "linear-search", "prompt": "Why can linear search work without sorting?", "options": ["It checks values one at a time", "It guesses the middle", "It swaps every pair"], "answer": "It checks values one at a time"},
                {"id": "ls-ret-2", "concept": "linear-search", "prompt": "What does the worst case require?", "options": ["Checking every value", "Checking only the first value", "Sorting twice"], "answer": "Checking every value"},
                {"id": "ls-ret-3", "concept": "linear-search", "prompt": "What does the current index identify?", "options": ["The value being checked", "The list's sort order", "The number of swaps"], "answer": "The value being checked"},
            ],
            "visualizer": {"kind": "linear", "values": [8, 3, 5, 7], "target": 5}
        },
        "binary-search": {
            "pre": [
                {"id": "bs-pre-2", "concept": "binary-search", "prompt": "Which bound moves when the target is larger than middle?", "options": ["Low moves right", "High moves right", "The list is shuffled"], "answer": "Low moves right"},
                {"id": "bs-pre-3", "concept": "binary-search", "prompt": "What does each comparison remove?", "options": ["About half the candidates", "All candidates", "Only the target"], "answer": "About half the candidates"},
            ],
            "checkpoint": [
                {"id": "bs-check-3", "concept": "binary-search", "prompt": "If target equals middle, what happens?", "options": ["Return the middle index", "Discard the list", "Move low left"], "answer": "Return the middle index"},
                {"id": "bs-check-4", "concept": "binary-search", "prompt": "When does the search stop without a match?", "options": ["Low passes high", "The list doubles", "Middle is always zero"], "answer": "Low passes high"},
                {"id": "bs-check-5", "concept": "binary-search", "prompt": "Which input breaks the sorted-order assumption?", "options": ["[4, 2, 8]", "[2, 4, 8]", "[]"], "answer": "[4, 2, 8]"},
                {"id": "bs-check-6", "concept": "binary-search", "prompt": "What does high mark?", "options": ["The last possible index", "The target value", "The number of swaps"], "answer": "The last possible index"},
            ],
            "post": [
                {"id": "bs-post-2", "concept": "binary-search", "prompt": "What happens to the candidate range after each unequal comparison?", "options": ["It shrinks", "It stays identical", "It becomes unsorted"], "answer": "It shrinks"},
                {"id": "bs-post-3", "concept": "binary-search", "prompt": "Which result means the target was absent?", "options": ["The bounds cross", "Middle is first", "Low equals high once"], "answer": "The bounds cross"},
            ],
            "follow_up": [
                {"id": "bs-follow-1", "concept": "binary-search", "prompt": "In [10, 20, 30, 40, 50], which value is the first middle?", "options": ["30", "10", "50"], "answer": "30"},
                {"id": "bs-follow-2", "concept": "binary-search", "prompt": "If target is smaller than middle, which bound moves?", "options": ["High moves left", "Low moves right", "Neither ever moves"], "answer": "High moves left"},
            ],
            "follow_up_repeat": [
                {"id": "bs-follow-repeat-1", "concept": "binary-search", "prompt": "In [3, 6, 9, 12, 15], what is the first middle value?", "options": ["9", "3", "15"], "answer": "9"},
                {"id": "bs-follow-repeat-2", "concept": "binary-search", "prompt": "If the target is larger than middle, which bound moves right?", "options": ["Low", "High", "Neither"], "answer": "Low"},
            ],
            "retention": [
                {"id": "bs-ret-1", "concept": "binary-search", "prompt": "What enables binary search to discard a half?", "options": ["Sorted order", "Random swaps", "A webcam"], "answer": "Sorted order"},
                {"id": "bs-ret-2", "concept": "binary-search", "prompt": "What happens to the candidate range after a comparison?", "options": ["It becomes smaller", "It always doubles", "It is shuffled"], "answer": "It becomes smaller"},
                {"id": "bs-ret-3", "concept": "binary-search", "prompt": "When is the target absent?", "options": ["Low passes high", "The first value is small", "The list has an even length"], "answer": "Low passes high"},
            ],
            "visualizer": {"kind": "binary", "values": [2, 4, 6, 8, 10, 12, 14], "target": 10}
        },
        "bubble-sort": {
            "pre": [
                {"id": "bub-pre-2", "concept": "bubble-sort", "prompt": "What does a swap change?", "options": ["The order of two neighbors", "The list length", "The target value"], "answer": "The order of two neighbors"},
                {"id": "bub-pre-3", "concept": "bubble-sort", "prompt": "What does one complete pass guarantee?", "options": ["The largest remaining value reaches the end", "The list is always fully sorted", "No comparisons happen"], "answer": "The largest remaining value reaches the end"},
            ],
            "checkpoint": [
                {"id": "bub-check-3", "concept": "bubble-sort", "prompt": "Which pair should swap in [4, 2]?", "options": ["4 and 2", "No pair", "Only the first with itself"], "answer": "4 and 2"},
                {"id": "bub-check-4", "concept": "bubble-sort", "prompt": "Which direction does a large value move during a pass?", "options": ["Right", "Left", "It disappears"], "answer": "Right"},
                {"id": "bub-check-5", "concept": "bubble-sort", "prompt": "What can an early-stop flag record?", "options": ["Whether any swap occurred", "The webcam state", "The target index"], "answer": "Whether any swap occurred"},
                {"id": "bub-check-6", "concept": "bubble-sort", "prompt": "What happens on an already sorted list with early stop?", "options": ["One pass and stop", "Always n² passes", "The list reverses"], "answer": "One pass and stop"},
            ],
            "post": [
                {"id": "bub-post-2", "concept": "bubble-sort", "prompt": "What does a no-swap pass tell us?", "options": ["The list is sorted", "The list is empty", "The largest value was deleted"], "answer": "The list is sorted"},
                {"id": "bub-post-3", "concept": "bubble-sort", "prompt": "Why does bubble sort need repeated passes?", "options": ["One pass fixes only a suffix position at a time", "It has no comparisons", "It searches the middle"], "answer": "One pass fixes only a suffix position at a time"},
            ],
            "follow_up": [
                {"id": "bub-follow-1", "concept": "bubble-sort", "prompt": "In [3, 1], what is the first action?", "options": ["Swap 3 and 1", "Delete 1", "Stop"], "answer": "Swap 3 and 1"},
                {"id": "bub-follow-2", "concept": "bubble-sort", "prompt": "When can a pass avoid another pass?", "options": ["When it made no swaps", "When it saw a large value", "When the first pair matched"], "answer": "When it made no swaps"},
            ],
            "follow_up_repeat": [
                {"id": "bub-follow-repeat-1", "concept": "bubble-sort", "prompt": "In [4, 2, 3], which pair is compared first?", "options": ["4 and 2", "2 and 3", "4 and 3"], "answer": "4 and 2"},
                {"id": "bub-follow-repeat-2", "concept": "bubble-sort", "prompt": "What does a complete pass move toward the right edge?", "options": ["The largest remaining value", "The smallest value", "The first pair only"], "answer": "The largest remaining value"},
            ],
            "retention": [
                {"id": "bub-ret-1", "concept": "bubble-sort", "prompt": "Which values are compared directly?", "options": ["Neighbors", "Only endpoints", "Random distant values"], "answer": "Neighbors"},
                {"id": "bub-ret-2", "concept": "bubble-sort", "prompt": "What does a swap change?", "options": ["The order of adjacent values", "The list length", "The number of inputs"], "answer": "The order of adjacent values"},
                {"id": "bub-ret-3", "concept": "bubble-sort", "prompt": "When can bubble sort stop early?", "options": ["A full pass makes no swaps", "The first pair swaps", "The list has four values"], "answer": "A full pass makes no swaps"},
            ],
            "visualizer": {"kind": "bubble", "values": [5, 2, 4, 1]}
        }
    }
    for lesson_id, additions in extras.items():
        row = conn.execute("SELECT payload FROM lessons WHERE id=?", (lesson_id,)).fetchone()
        if not row:
            continue
        payload = json.loads(row["payload"])
        if "visualizer" in additions:
            payload["visualizer"] = additions["visualizer"]
        for bank, items in additions.items():
            if bank in {"pre", "checkpoint", "post", "follow_up", "follow_up_repeat", "retention"}:
                existing_ids = {q["id"] for q in payload.setdefault("questions", {}).setdefault(bank, [])}
                payload["questions"][bank].extend(item for item in items if item["id"] not in existing_ids)
        conn.execute("UPDATE lessons SET payload=? WHERE id=?", (json.dumps(payload), lesson_id))


def row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None
