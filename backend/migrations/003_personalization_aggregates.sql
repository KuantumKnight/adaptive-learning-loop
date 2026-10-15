-- Completed support outcomes kept by participant, reset boundary, concept, and kind.
CREATE TABLE IF NOT EXISTS personalization_aggregates (
    id SERIAL PRIMARY KEY,
    participant_id INTEGER NOT NULL REFERENCES participants(id),
    reset_group TEXT NOT NULL DEFAULT 'default',
    mode TEXT NOT NULL,
    concept TEXT NOT NULL,
    kind TEXT NOT NULL,
    completed_interventions INTEGER NOT NULL DEFAULT 0,
    outcome_sum DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(participant_id, reset_group, mode, concept, kind)
);
CREATE INDEX IF NOT EXISTS idx_personalization_aggregates_lookup
    ON personalization_aggregates(participant_id, reset_group, concept, mode);
