CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_intervention
ON interventions(session_id)
WHERE status IN ('offered', 'viewed', 'accepted');
