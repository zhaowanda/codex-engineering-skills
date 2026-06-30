#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-implement-dry-run-v1"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def collect_plan_scope(plan: dict[str, Any]) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    allowed_files: list[str] = []
    test_commands: list[str] = []
    repo_tasks: list[dict[str, Any]] = []
    for task in as_list(plan.get("repo_tasks")):
        if not isinstance(task, dict):
            continue
        if task.get("role") == "modify":
            allowed_files.extend(str(item) for item in as_list(task.get("allowed_files")) if item)
            test_commands.extend(str(item) for item in as_list(task.get("test_commands")) if item)
            repo_tasks.append({
                "repo": task.get("repo", ""),
                "repo_path": task.get("repo_path", ""),
                "allowed_files": as_list(task.get("allowed_files")),
                "test_commands": as_list(task.get("test_commands")),
            })
    return sorted(set(allowed_files)), sorted(set(test_commands)), repo_tasks


def decision_ready(data: dict[str, Any], accepted: set[str]) -> bool:
    decision = str(data.get("decision") or data.get("status") or "")
    if not data:
        return False
    if decision and decision not in accepted:
        return False
    return not any(data.get(key) for key in ["blockers", "active_blockers", "missing_evidence"])


def run(artifact_dir: Path) -> dict[str, Any]:
    plan = load_json(artifact_dir / "delivery_plan.json")
    edit_permit = load_json(artifact_dir / "edit_permit.json")
    git_evidence = load_json(artifact_dir / "git_worktree_evidence.json")
    delivery_status = load_json(artifact_dir / "delivery_status.json")
    allowed_files, test_commands, repo_tasks = collect_plan_scope(plan)
    missing_gates: list[str] = []
    if not decision_ready(git_evidence, {"ready", "pass"}):
        missing_gates.append("git_worktree_evidence.json")
    if not decision_ready(edit_permit, {"ready", "pass"}):
        missing_gates.append("edit_permit.json")
    if not plan:
        missing_gates.append("delivery_plan.json")
    if not allowed_files:
        missing_gates.append("delivery_plan.allowed_files")
    can_edit = not missing_gates and bool(allowed_files)
    return {
        "schema": SCHEMA,
        "artifact_dir": str(artifact_dir),
        "decision": "ready" if can_edit else "blocked",
        "dry_run": True,
        "can_edit": can_edit,
        "allowed_files": allowed_files,
        "forbidden_files": ["files outside delivery_plan.repo_tasks[].allowed_files"],
        "recommended_validation_commands": test_commands,
        "repo_tasks": repo_tasks,
        "missing_gates": missing_gates,
        "delivery_next_action_type": delivery_status.get("next_action_type", ""),
        "next_action": "Proceed with scoped implementation only." if can_edit else "Complete missing gates before editing.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run implementation readiness from delivery artifacts")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    result = run(Path(args.artifact_dir))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
