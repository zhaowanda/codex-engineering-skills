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


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture delivery case summary")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = capture(Path(args.artifact_dir), args.case_id)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
