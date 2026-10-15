-- Query indexes used by history, event idempotency, and research exports.
CREATE INDEX IF NOT EXISTS idx_sessions_participant_mode ON sessions(participant_id, mode, reset_group);
CREATE INDEX IF NOT EXISTS idx_answers_session_phase ON answers(session_id, phase);
CREATE INDEX IF NOT EXISTS idx_interventions_session_status ON interventions(session_id, status);
CREATE INDEX IF NOT EXISTS idx_follow_ups_intervention ON follow_ups(intervention_id);
