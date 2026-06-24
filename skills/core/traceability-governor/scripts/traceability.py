#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-traceability-matrix-v1"


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


def changed_files_from_diff(diff: str) -> list[str]:
    files: list[str] = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            if path != "/dev/null":
                files.append(path)
    return sorted(set(files))


def changed_files(artifact_dir: Path, implementation: dict[str, Any]) -> list[str]:
    files = [str(item) for item in as_list(implementation.get("changed_files")) if item]
    if files:
        return sorted(set(files))
    diff_path = artifact_dir / "change.diff"
    if diff_path.exists():
        return changed_files_from_diff(diff_path.read_text(encoding="utf-8", errors="ignore"))
    return []


def allowed_files(plan: dict[str, Any]) -> list[str]:
    files: list[str] = []
    for task in as_list(plan.get("repo_tasks")):
        if isinstance(task, dict):
            files.extend(str(item) for item in as_list(task.get("allowed_files")) if item)
    return sorted(set(files))


def file_in_scope(path: str, scopes: list[str]) -> bool:
    normalized = path.strip("/")
    for scope in scopes:
        clean = str(scope).strip("/")
        if clean and (normalized.startswith(clean) or clean in normalized):
            return True
    return False


def build(artifact_dir: Path) -> dict[str, Any]:
    spec = load_json(artifact_dir / "spec.json")
    technical = load_json(artifact_dir / "technical_design.json")
    architecture = load_json(artifact_dir / "architecture_design.json")
    plan = load_json(artifact_dir / "delivery_plan.json")
    test_design = load_json(artifact_dir / "test_design.json")
    implementation = load_json(artifact_dir / "implementation_completion_gate.json")
    test_gate = load_json(artifact_dir / "test_evidence_gate.json")
    release_gate = load_json(artifact_dir / "release_gate.json")

    requirements = [item for item in as_list(spec.get("requirements")) if isinstance(item, dict)]
    acceptance = [item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]
    tests = [item for item in as_list(test_design.get("test_cases")) if isinstance(item, dict)]
    tasks = [item for item in as_list(plan.get("repo_tasks")) if isinstance(item, dict)]
    files = changed_files(artifact_dir, implementation)
    scopes = allowed_files(plan)

    test_by_ac: dict[str, list[str]] = {}
    for case in tests:
        ac_id = str(case.get("acceptance_id") or "")
        if ac_id:
            test_by_ac.setdefault(ac_id, []).append(str(case.get("id") or "unnamed-test"))

    ac_rows: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for idx, ac in enumerate(acceptance):
        ac_id = str(ac.get("id") or f"AC-{idx + 1}")
        mapped_tests = sorted(set(test_by_ac.get(ac_id, [])))
        row = {
            "acceptance_id": ac_id,
            "summary": ac.get("criteria") or ac.get("summary") or "",
            "mapped_tests": mapped_tests,
            "evidence_required": as_list(ac.get("evidence_required")),
            "covered": bool(mapped_tests),
        }
        ac_rows.append(row)
        if not mapped_tests:
            blockers.append({"source": "acceptance_criteria", "message": "acceptance criterion has no mapped test", "acceptance_id": ac_id})

    task_rows: list[dict[str, Any]] = []
    for idx, task in enumerate(tasks):
        task_id = str(task.get("id") or task.get("task_id") or f"TASK-{idx + 1}")
        allowed = [str(item) for item in as_list(task.get("allowed_files")) if item]
        validation = as_list(task.get("validation")) or as_list(task.get("validation_evidence"))
        role = str(task.get("role") or task.get("change_type") or "")
        row = {
            "task_id": task_id,
            "repo": task.get("repo") or task.get("project") or "",
            "role": role,
            "allowed_files": allowed,
            "validation": validation,
            "traceable": bool(allowed and validation),
        }
        task_rows.append(row)
        if role == "modify" and not allowed:
            blockers.append({"source": "delivery_plan", "message": "modify task has no allowed_files", "task_id": task_id})
        if role == "modify" and not validation:
            warnings.append({"source": "delivery_plan", "message": "modify task has no validation evidence", "task_id": task_id})

    out_of_scope = [file for file in files if scopes and not file_in_scope(file, scopes)]
    if files and not plan:
        blockers.append({"source": "delivery_plan", "message": "changed files exist but delivery_plan.json is missing"})
    if out_of_scope:
        blockers.append({"source": "changed_files", "message": "changed files outside allowed scope", "files": out_of_scope})
    if not technical:
        warnings.append({"source": "technical_design", "message": "technical_design.json is missing"})
    if not architecture:
        warnings.append({"source": "architecture_design", "message": "architecture_design.json is missing"})
    if release_gate and release_gate.get("decision") == "go" and blockers:
        blockers.append({"source": "release_gate", "message": "release go is invalid while traceability blockers exist"})

    coverage = {
        "requirement_count": len(requirements),
        "acceptance_count": len(acceptance),
        "covered_acceptance_count": sum(1 for row in ac_rows if row["covered"]),
        "task_count": len(task_rows),
        "traceable_task_count": sum(1 for row in task_rows if row["traceable"]),
        "changed_file_count": len(files),
    }
    return {
        "schema": SCHEMA,
        "doc_id": spec.get("doc_id") or technical.get("doc_id") or architecture.get("doc_id"),
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "coverage": coverage,
        "acceptance_trace": ac_rows,
        "task_trace": task_rows,
        "changed_files": files,
        "out_of_scope_files": out_of_scope,
        "test_gate_decision": test_gate.get("decision") or test_gate.get("status") or "",
        "blockers": blockers,
        "warnings": warnings,
        "next_action": "Fix traceability blockers before implementation/release." if blockers else "Use this matrix as release evidence.",
    }


def validate(data: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if data.get("schema") != SCHEMA:
        issues.append(f"schema must be {SCHEMA}")
    if data.get("decision") not in {"pass", "warn", "block"}:
        issues.append("decision must be pass/warn/block")
    if data.get("decision") == "pass" and (data.get("blockers") or data.get("warnings")):
        issues.append("pass is not allowed with blockers or warnings")
    if data.get("decision") == "block" and not data.get("blockers"):
        issues.append("block decision requires blockers")
    return not issues, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Build requirement-to-delivery traceability matrix")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--out")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    result = build(Path(args.artifact_dir))
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.validate:
        ok, issues = validate(result)
        if not ok:
            print(json.dumps({"schema": "codex-traceability-validation-v1", "valid": ok, "issues": issues}, ensure_ascii=False, indent=2))
            return 1
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
