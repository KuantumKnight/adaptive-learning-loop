# Repeatable demonstration script

This script is for a technical demonstration, not a participant result.
Create a fresh participant code such as `demo-01`; do not reuse volunteer
codes. If a history is needed, label the session as practice or
`synthetic_demo` in the research record.

1. Start the backend and frontend with the README commands. Confirm `/health/ready`.
2. Choose Binary Search, participant `demo-01`, and Personalized adaptive.
3. Complete the three baseline questions and inspect the lesson visualizer.
4. Open the lesson section tabs, step the visualizer, and continue to checkpoints.
5. Submit two incorrect checkpoint answers. Read the displayed reason and
   accept the simplified explanation.
6. Complete both distinct follow-up checks. Show the support status in the
   results/history record and download the session CSV.
7. Exit and create another Personalized session for `demo-01`. Request help
   explicitly. Show the worked-example selection and its history reason.
8. Open the researcher workspace with the local researcher credential and
   show provenance, versions, completeness, and export columns.
9. For an outage demonstration, stop the API after the session opens. Wait for
   the header to show pending events, restart the API, and wait for `saved`.
10. State clearly which records are observed technical demonstrations and
    which, if any, are synthetic. Never present them as volunteer findings.

The deterministic rehearsal artifact is generated with
`python scripts/generate-synthetic-demo.py` and lives under
`artifacts/synthetic-demo/`. Its manifest sets `data_origin` to
`synthetic_demo`, marks `human_participant` false, and excludes it from study
summaries. The study-chart generator must reject this file.

Backup recording is an external deliverable. If no recording is made, report
that fact rather than claiming video completion.
