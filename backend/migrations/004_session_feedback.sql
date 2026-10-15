-- Optional post-session usability feedback. Free text stays out of study CSV exports.
CREATE TABLE IF NOT EXISTS session_feedback (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE REFERENCES sessions(id),
    usability_rating INTEGER,
    ease_rating INTEGER,
    comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
