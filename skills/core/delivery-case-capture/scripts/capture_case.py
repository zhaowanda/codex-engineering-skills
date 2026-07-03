#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ARTIFACTS = ["spec.json", "technical_design.json", "architecture_design.json", "delivery_plan.json", "design_architecture_review.json", "code_review_gate.json", "test_evidence_gate.json", "release_gate.json"]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def summarize(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": data.get("schema", ""),
        "decision": data.get("decision", data.get("status", "")),
        "blocker_count": len(data.get("blockers", []) if isinstance(data.get("blockers"), list) else []),
        "warning_count": len(data.get("warnings", []) if isinstance(data.get("warnings"), list) else []),
    }


def capture(artifact_dir: Path, case_id: str) -> dict[str, Any]:
    summaries = {}
    blockers = []
    for name in ARTIFACTS:
        data = load_json(artifact_dir / name)
        if data:
            summaries[name] = summarize(data)
            if data.get("blockers"):
                blockers.append({"artifact": name, "blockers": data.get("blockers")})
    return {
        "schema": "codex-delivery-case-v1",
        "case_id": case_id,
        "artifact_dir": str(artifact_dir),
        "artifact_summaries": summaries,
        "blockers_observed": blockers,
        "lessons": [],
        "skill_improvement_candidates": [],
        "privacy_note": "Review before sharing; keep real project/customer details in private overlays.",
    }


def replay_skeleton(artifact_dir: Path, case_id: str) -> dict[str, Any]:
    case = capture(artifact_dir, case_id)
    artifacts = []
    for name, summary in case["artifact_summaries"].items():
        artifacts.append({
            "artifact": name,
            "schema": summary.get("schema", ""),
            "decision": summary.get("decision", ""),
            "blocker_count": summary.get("blocker_count", 0),
            "warning_count": summary.get("warning_count", 0),
        })
    return {
        "schema": "codex-delivery-replay-skeleton-v1",
        "case_id": case_id,
        "anonymized": True,
        "source": "artifact_summaries_only",
        "artifacts": artifacts,
        "replay_steps": [
            {"step": "ingest_requirement", "expected_artifact": "spec.json"},
            {"step": "review_design", "expected_artifact": "design_architecture_review.json"},
            {"step": "review_delivery", "expected_artifact": "delivery_plan.json"},
            {"step": "review_tests", "expected_artifact": "test_evidence_gate.json"},
            {"step": "bind_release", "expected_artifact": "release_gate.json"},
        ],
        "privacy_note": "No source text, customer names, repo paths, or local absolute paths are included.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture delivery case summary")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--replay-skeleton", action="store_true")
    args = parser.parse_args()
    result = replay_skeleton(Path(args.artifact_dir), args.case_id) if args.replay_skeleton else capture(Path(args.artifact_dir), args.case_id)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
