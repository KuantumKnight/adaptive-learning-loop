"""Create descriptive SVG charts from a real study CSV export.

The script intentionally refuses to create charts when no observed measured
rows are present. Practice, synthetic demonstration, and legacy records are
excluded by default so an empty pilot cannot accidentally become a fabricated
result.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def svg_bar_chart(path: Path, title: str, values: dict[str, int], color: str = "#19735f") -> None:
    width, height = 900, 460
    margin_left, margin_top, chart_height = 90, 82, 270
    maximum = max(values.values(), default=0) or 1
    bar_width = max(26, (width - margin_left - 50) // max(1, len(values)) - 18)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{title}</title><desc id="desc">Values derived from observed measured study rows.</desc>',
        '<rect width="100%" height="100%" fill="#f5f3ee"/>',
        f'<text x="{margin_left}" y="42" font-family="Arial,sans-serif" font-size="24" fill="#1d2b2b">{title}</text>',
        f'<line x1="{margin_left}" y1="{margin_top + chart_height}" x2="850" y2="{margin_top + chart_height}" stroke="#9eafaa"/>',
    ]
    for index, (label, value) in enumerate(values.items()):
        x = margin_left + 32 + index * ((width - margin_left - 50) // max(1, len(values)))
        bar_height = round(chart_height * value / maximum)
        y = margin_top + chart_height - bar_height
        parts.append(f'<rect x="{x}" y="{y}" width="{bar_width}" height="{bar_height}" fill="{color}"/>')
        parts.append(f'<text x="{x + bar_width / 2}" y="{y - 8}" text-anchor="middle" font-family="Arial,sans-serif" font-size="15" fill="#1d2b2b">{value}</text>')
        parts.append(f'<text x="{x + bar_width / 2}" y="{margin_top + chart_height + 26}" text-anchor="middle" font-family="Arial,sans-serif" font-size="13" fill="#526465">{label}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/study"))
    args = parser.parse_args()
    with args.csv_path.open(newline="", encoding="utf-8-sig") as handle:
        all_rows = list(csv.DictReader(handle))
    candidates = [row for row in all_rows if row.get("data_origin") == "observed" and row.get("study_kind") == "study"]
    by_session: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidates:
        if row.get("session_id"):
            by_session[row["session_id"]].append(row)
    excluded_incomplete = 0
    eligible_ids: set[str] = set()
    for sid, session_rows in by_session.items():
        phase_counts = Counter(row.get("phase") for row in session_rows if row.get("record_type") == "answer")
        if session_rows[0].get("ended_at") and phase_counts["pre"] == 3 and phase_counts["checkpoint"] == 6 and phase_counts["post"] == 3:
            eligible_ids.add(sid)
        else:
            excluded_incomplete += 1
    rows = [row for row in candidates if row.get("session_id") in eligible_ids]
    if not rows:
        raise SystemExit("No complete observed measured-study sessions found; refusing to chart practice, synthetic, or incomplete data.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    sessions: dict[str, dict[str, str]] = {}
    post_scores: dict[str, list[int]] = defaultdict(list)
    intervention_counts: Counter[str] = Counter()
    for row in rows:
        sid = row.get("session_id", "")
        sessions.setdefault(sid, {key: row.get(key, "") for key in ("participant_code", "mode", "lesson_id", "content_version", "policy_version")})
        if row.get("record_type") == "answer" and row.get("phase") == "post" and row.get("correct") in {"0", "1"}:
            post_scores[row.get("mode", "unknown")].append(int(row["correct"]))
        if row.get("record_type") == "intervention" and row.get("intervention_kind"):
            intervention_counts[row["intervention_kind"]] += 1

    summary = {
        "source_rows": len(rows),
        "session_count": len(sessions),
        "excluded_sessions": {"incomplete_or_unended": excluded_incomplete},
        "excluded_rows_outside_observed_study": len(all_rows) - len(candidates),
        "post_test_correct_by_mode": {mode: {"correct": sum(scores), "count": len(scores)} for mode, scores in sorted(post_scores.items())},
        "interventions_by_kind": dict(sorted(intervention_counts.items())),
        "filters": {"data_origin": "observed", "study_kind": "study", "ended_at": "present", "required_answer_counts": {"pre": 3, "checkpoint": 6, "post": 3}},
        "synthetic_or_practice_included": False,
    }
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    session_path = args.output_dir / "session-summaries.csv"
    with session_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["session_id", *next(iter(sessions.values())).keys()])
        writer.writeheader()
        for sid, metadata in sorted(sessions.items()):
            writer.writerow({"session_id": sid, **metadata})
    svg_bar_chart(args.output_dir / "post-test-correct-by-mode.svg", "Post-test correct responses by mode", {mode: data["correct"] for mode, data in summary["post_test_correct_by_mode"].items()})
    svg_bar_chart(args.output_dir / "interventions-by-kind.svg", "Observed interventions by kind", summary["interventions_by_kind"], color="#a84e25")
    print(f"Wrote descriptive charts and summaries for {len(sessions)} observed measured session(s) to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
