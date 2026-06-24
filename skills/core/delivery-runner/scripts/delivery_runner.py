#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ORDER = [
    ("spec", "spec.json"),
    ("technical_design", "technical_design.json"),
    ("architecture_design", "architecture_design.json"),
    ("delivery_plan", "delivery_plan.json"),
    ("design_review", "design_architecture_review.json"),
    ("git", "git_worktree_evidence.json"),
    ("edit_permit", "edit_permit.json"),
    ("implementation", "implementation_completion_gate.json"),
    ("review", "code_review_gate.json"),
    ("test", "test_evidence_gate.json"),
    ("environment", "environment_promotion.json"),
    ("uat", "uat_acceptance.json"),
    ("release_change", "release_change.json"),
    ("release", "release_gate.json"),
    ("post_release", "post_release_observation.json"),
]
IMPLEMENTATION_REQUIRED = ["spec", "technical_design", "architecture_design", "delivery_plan", "design_review", "git", "edit_permit"]
RELEASE_REQUIRED = ["implementation", "review", "test", "environment", "uat", "release_change", "release"]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def is_pass(data: dict[str, Any]) -> bool:
    decision = data.get("decision") or data.get("status")
    if decision in {"pass", "ready", "approve", "approved", "go"}:
        return True
    if data.get("pass") is True:
        return True
    return bool(data) and not any(data.get(key) for key in ["blockers", "active_blockers", "missing_evidence"])


def inspect(artifact_dir: Path) -> dict[str, Any]:
    artifacts: dict[str, dict[str, Any]] = {name: load_json(artifact_dir / filename) for name, filename in ORDER}
    state = load_json(artifact_dir / "delivery_state.json")
    completed = [name for name, _ in ORDER if is_pass(artifacts[name])]
    missing = [name for name, _ in ORDER if not artifacts[name]]
    blockers: list[dict[str, Any]] = []
    for name, data in artifacts.items():
        if not data:
            continue
        for key in ["blockers", "active_blockers", "missing_evidence"]:
            if data.get(key):
                blockers.append({"source": name, "message": f"{key} present", "count": len(data.get(key) if isinstance(data.get(key), list) else [data.get(key)])})
        if data.get("decision") in {"block", "blocked", "no_go", "fail", "failed", "request_changes", "needs_revision"}:
            blockers.append({"source": name, "message": f"blocking decision: {data.get('decision')}"})
    if state.get("blockers"):
        blockers.append({"source": "delivery_state", "message": "delivery state has blockers", "count": len(state.get("blockers", []))})

    next_stage = "done"
    for name, _ in ORDER:
        if name not in completed:
            next_stage = name
            break
    implementation_missing = [name for name in IMPLEMENTATION_REQUIRED if name not in completed]
    release_missing = [name for name in RELEASE_REQUIRED if name not in completed]
    can_implement = not implementation_missing and not blockers
    can_release = not release_missing and not blockers
    commands = {
        "spec": "python3 skills/core/spec-governor/scripts/spec_governor.py normalize --doc-id REQ-001 --title \"Title\" --input requirement.txt --out artifacts/REQ-001/spec.json",
        "technical_design": "python3 skills/core/technical-design-governor/scripts/technical_design.py --spec artifacts/REQ-001/spec.json --out artifacts/REQ-001/technical_design.json",
        "architecture_design": "python3 skills/core/architecture-design-governor/scripts/architecture_design.py --spec artifacts/REQ-001/spec.json --technical-design artifacts/REQ-001/technical_design.json --out artifacts/REQ-001/architecture_design.json",
        "delivery_plan": "python3 skills/templates/delivery-plan-templates/scripts/render_delivery_plan.py --doc-id REQ-001 --technical-design artifacts/REQ-001/technical_design.json --architecture-design artifacts/REQ-001/architecture_design.json --out artifacts/REQ-001/delivery_plan.json",
        "design_review": "python3 skills/core/design-architecture-reviewer/scripts/design_arch_review.py --technical-design artifacts/REQ-001/technical_design.json --architecture-design artifacts/REQ-001/architecture_design.json --out artifacts/REQ-001/design_architecture_review.json",
        "environment": "python3 skills/core/environment-promotion-governor/scripts/environment_promotion.py template --out artifacts/REQ-001/environment_promotion.json",
        "uat": "python3 skills/core/uat-acceptance-governor/scripts/uat_acceptance.py template --out artifacts/REQ-001/uat_acceptance.json",
        "release_change": "python3 skills/core/release-change-governor/scripts/release_change.py template --out artifacts/REQ-001/release_change.json",
        "post_release": "python3 skills/core/post-release-observer/scripts/post_release_observer.py template --out artifacts/REQ-001/post_release_observation.json",
    }
    return {
        "schema": "codex-delivery-runner-status-v1",
        "artifact_dir": str(artifact_dir),
        "state_present": bool(state),
        "completed_stages": completed,
        "missing_artifacts": missing,
        "blockers": blockers,
        "next_stage": next_stage,
        "next_command": commands.get(next_stage, "Run the gate for the next missing stage and attach evidence."),
        "can_implement": can_implement,
        "can_release": can_release,
        "implementation_missing": implementation_missing,
        "release_missing": release_missing,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect delivery workflow status")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_inspect = sub.add_parser("inspect")
    p_inspect.add_argument("--artifact-dir", required=True)
    p_inspect.add_argument("--out")
    args = parser.parse_args()
    result = inspect(Path(args.artifact_dir))
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["blockers"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
