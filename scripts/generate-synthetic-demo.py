"""Write a clearly labelled synthetic session for the technical demo.

This artifact is intentionally separate from the research export path. It is
useful for rehearsing the personalized-support story when no participant
history exists, but it must never be passed to the study-chart generator or
reported as a human observation.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


HEADERS = [
    "session_id", "participant_code", "session_kind", "mode", "lesson_id",
    "data_origin", "content_version", "policy_version", "record_type",
    "phase", "concept", "correct", "intervention_kind", "intervention_status",
    "follow_up_correct", "selection_reason", "completeness",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/synthetic-demo"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    session_id = "synthetic-demo-personalized-001"
    rows = [
        {
            "session_id": session_id, "participant_code": "SYNTHETIC-DEMO",
            "session_kind": "practice", "mode": "personalized", "lesson_id": "binary-search",
            "data_origin": "synthetic_demo", "content_version": "v2", "policy_version": "v2",
            "record_type": "answer", "phase": "checkpoint", "concept": "binary-search",
            "correct": "0", "intervention_kind": "simplified", "intervention_status": "completed",
            "follow_up_correct": "", "selection_reason": "initial default", "completeness": "complete",
        },
        {
            "session_id": session_id, "participant_code": "SYNTHETIC-DEMO",
            "session_kind": "practice", "mode": "personalized", "lesson_id": "binary-search",
            "data_origin": "synthetic_demo", "content_version": "v2", "policy_version": "v2",
            "record_type": "intervention", "phase": "", "concept": "binary-search",
            "correct": "", "intervention_kind": "simplified", "intervention_status": "completed",
            "follow_up_correct": "1/2", "selection_reason": "initial default", "completeness": "complete",
        },
        {
            "session_id": session_id, "participant_code": "SYNTHETIC-DEMO",
            "session_kind": "practice", "mode": "personalized", "lesson_id": "binary-search",
            "data_origin": "synthetic_demo", "content_version": "v2", "policy_version": "v2",
            "record_type": "next-session-choice", "phase": "", "concept": "binary-search",
            "correct": "", "intervention_kind": "worked_example", "intervention_status": "offered",
            "follow_up_correct": "", "selection_reason": "exploration of an unused support type", "completeness": "complete",
        },
    ]
    csv_path = args.output_dir / "synthetic-session-export.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    manifest = {
        "data_origin": "synthetic_demo",
        "participant_code": "SYNTHETIC-DEMO",
        "session_id": session_id,
        "purpose": "Rehearse the technical personalized-support demonstration only.",
        "human_participant": False,
        "include_in_study_summary": False,
        "generated_by": "scripts/generate-synthetic-demo.py",
        "warning": "This file contains invented values and must never be reported as a participant result.",
    }
    (args.output_dir / "README.md").write_text(
        "# Synthetic demonstration data\n\n"
        "This folder is an explicitly labelled rehearsal artifact. It is not a human study result.\n\n"
        "The CSV shows a synthetic personalized-support history and is excluded from the study chart generator.\n",
        encoding="utf-8",
    )
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote labelled synthetic demo data to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
