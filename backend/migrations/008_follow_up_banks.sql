ALTER TABLE interventions ADD COLUMN IF NOT EXISTS follow_up_bank TEXT NOT NULL DEFAULT 'follow_up';
