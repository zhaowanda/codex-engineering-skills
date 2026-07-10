#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-delivery-plan-review-v1"
BROAD_SCOPE = {".", "*", "src", "app", "services", "packages", "frontend", "backend"}
GENERIC_TASK_PHRASES = {
    "modify only allowed_files",
    "record command output",
    "build concrete change list from reviewed design before editing",
    "confirm no extra repositories or broad files are needed",
    "preserve compatibility and permission behavior from design",
}
PHASE_SIGNALS = {
    "read": ("read", "inspect", "understand", "确认", "阅读"),
    "confirm": ("confirm", "verify contract", "route", "scope", "确认"),
    "edit": ("edit", "implement", "change", "modify", "实现", "修改"),
    "test": ("test", "pytest", "unit", "integration", "browser", "测试"),
    "evidence": ("evidence", "screenshot", "log", "artifact", "证据"),
    "rollback": ("rollback", "revert", "restore", "回滚"),
}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"JSON root must be object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def finding(area: str, severity: str, message: str, evidence: Any, suggestion: str) -> dict[str, Any]:
    return {"area": area, "severity": severity, "message": message, "evidence": evidence, "suggestion": suggestion}


def text_of(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).lower()


def looks_like_path(value: str) -> bool:
    text = value.strip()
    return "/" in text or "." in Path(text).name


def generic_task_detail(value: Any) -> bool:
    blob = text_of(value)
    return any(phrase in blob for phrase in GENERIC_TASK_PHRASES)


def phase_coverage(tasks: list[Any]) -> dict[str, bool]:
    blob = text_of(tasks)
    return {phase: any(signal in blob for signal in signals) for phase, signals in PHASE_SIGNALS.items()}


def score(findings: list[dict[str, Any]]) -> int:
    weights = {"blocker": 30, "high": 12, "medium": 5, "low": 2}
    return max(0, 100 - sum(weights.get(str(item.get("severity")), 0) for item in findings))


def role_repos(plan: dict[str, Any], role: str) -> list[str]:
    repos = []
    for item in as_list(plan.get("repo_tasks")):
        if isinstance(item, dict) and item.get("role") == role and item.get("repo"):
            repos.append(str(item["repo"]))
    return repos


def review(plan: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    if plan.get("schema") != "codex-delivery-plan-v1":
        findings.append(finding("schema", "blocker", "delivery plan schema is invalid", plan.get("schema"), "Use codex-delivery-plan-v1."))
    source_design_gate = plan.get("source_design_gate") if isinstance(plan.get("source_design_gate"), dict) else {}
    if source_design_gate.get("design_allowed") is False:
        findings.append(finding("gates", "blocker", "source design requirement understanding gate blocks delivery planning", source_design_gate, "Resolve requirement clarification blockers and rerun design review before creating executable delivery tasks."))
    if source_design_gate.get("implementation_allowed") is False:
        findings.append(finding("gates", "blocker", "source design requirement understanding gate blocks implementation", source_design_gate, "Do not start Git preparation or edits until requirement understanding allows implementation."))
    if as_list(plan.get("open_gates")):
        findings.append(finding("gates", "blocker", "delivery plan has unresolved open gates", plan.get("open_gates"), "Resolve open_gates before Git preparation or implementation."))

    repo_tasks = [item for item in as_list(plan.get("repo_tasks")) if isinstance(item, dict)]
    if not repo_tasks:
        findings.append(finding("repo_tasks", "blocker", "repo_tasks is missing", plan.get("repo_tasks"), "Add repository tasks with explicit roles."))

    modify_repos = role_repos(plan, "modify")
    for idx, task in enumerate(repo_tasks):
        repo = str(task.get("repo") or f"repo_tasks[{idx}]")
        role = task.get("role")
        if role != "modify":
            continue
        tasks = as_list(task.get("tasks"))
        allowed_files = [str(item) for item in as_list(task.get("allowed_files")) if str(item).strip()]
        read_first = [str(item) for item in as_list(task.get("read_first")) if str(item).strip()]
        tests = [str(item) for item in as_list(task.get("test_commands")) if str(item).strip()]
        acceptance = as_list(task.get("acceptance_evidence"))
        rollback = as_list(task.get("rollback"))
        risks = as_list(task.get("risks"))
        if not task.get("repo_path"):
            findings.append(finding("repo_scope", "blocker", "modify repo lacks repo_path", repo, "Set repo_path before git-worktree-governor."))
        if not tasks:
            findings.append(finding("task_depth", "blocker", "modify repo lacks executable tasks", repo, "Add read/confirm/edit/test/evidence/rollback tasks."))
        elif len(tasks) < 2:
            findings.append(finding("task_depth", "high", "modify repo task list is too coarse", {"repo": repo, "task_count": len(tasks)}, "Split work into implementation phases with exit criteria."))
        if not any(looks_like_path(item) for item in allowed_files):
            findings.append(finding("file_scope", "high", "allowed_files lacks concrete file paths", {"repo": repo, "allowed_files": allowed_files}, "Use real file paths from code index or explicit human confirmation."))
        for task_index, item in enumerate(tasks):
            if not isinstance(item, dict):
                findings.append(finding("task_depth", "high", "task must be structured", {"repo": repo, "task_index": task_index}, "Use structured task objects with phase, files, evidence, and exit criteria."))
                continue
            required_task_fields = ["phase", "summary", "implementation_notes", "evidence_to_collect", "rollback_check", "exit_criteria"]
            missing_task_fields = [field for field in required_task_fields if item.get(field) in (None, "", [], {})]
            phase = str(item.get("phase") or "")
            if phase in {"read", "confirm"} and not item.get("files_to_read"):
                missing_task_fields.append("files_to_read")
            if phase == "edit" and not item.get("files_to_edit"):
                missing_task_fields.append("files_to_edit")
            if phase not in {"read"} and not item.get("depends_on"):
                missing_task_fields.append("depends_on")
            if not item.get("blocking_conditions"):
                missing_task_fields.append("blocking_conditions")
            if item.get("files_to_edit") and not any(looks_like_path(str(path)) for path in as_list(item.get("files_to_edit"))):
                missing_task_fields.append("concrete files_to_edit")
            if missing_task_fields:
                findings.append(finding("task_depth", "high", "task lacks executable detail", {"repo": repo, "task_id": item.get("task_id"), "missing": sorted(set(missing_task_fields))}, "Each task needs concrete files, implementation notes, evidence, rollback check, dependencies, blockers, and exit criteria."))
            if generic_task_detail(item.get("implementation_notes")) and len(as_list(item.get("implementation_notes"))) <= 2:
                findings.append(finding("task_depth", "medium", "task implementation notes are generic", {"repo": repo, "task_id": item.get("task_id"), "implementation_notes": item.get("implementation_notes")}, "Add file/function/route/config specific implementation notes."))
        phases = phase_coverage(tasks)
        missing_phases = [phase for phase, covered in phases.items() if not covered]
        if missing_phases:
            findings.append(finding("task_depth", "medium", "task list misses execution phases", {"repo": repo, "missing_phases": missing_phases}, "Include read, confirm, edit, test, evidence, and rollback verification steps."))
        if not allowed_files:
            findings.append(finding("file_scope", "blocker", "modify repo lacks allowed_files", repo, "Bind a narrow file scope for edit-readiness and write guard."))
        elif any(item in BROAD_SCOPE or item.endswith("/") for item in allowed_files):
            findings.append(finding("file_scope", "high", "allowed_files contains broad scope", {"repo": repo, "allowed_files": allowed_files}, "Use concrete directories or files close to the change."))
        if not read_first:
            findings.append(finding("readiness", "high", "modify repo lacks read_first", repo, "List files/modules to inspect before editing."))
        if not tests:
            findings.append(finding("validation", "high", "modify repo lacks test_commands", repo, "Bind concrete local test commands."))
        if not acceptance:
            findings.append(finding("validation", "high", "modify repo lacks acceptance evidence mapping", repo, "Map AC ids to required evidence."))
        if not rollback:
            findings.append(finding("rollback", "high", "modify repo lacks rollback steps", repo, "Add repo-specific rollback steps and data risk."))
        if not risks:
            findings.append(finding("risk", "medium", "modify repo lacks risk controls", repo, "Record delivery risks and mitigations."))
        git_prep = task.get("git_preparation") if isinstance(task.get("git_preparation"), dict) else {}
        required_git = text_of(git_prep.get("required_before_edit", []))
        for signal in ["fetch", "pull --ff-only", "branch", "clean worktree"]:
            if signal not in required_git:
                findings.append(finding("readiness", "high", "git preparation is incomplete", {"repo": repo, "missing_signal": signal}, "Require fetch, pull --ff-only, branch preparation, and clean worktree verification before edits."))

    validation = plan.get("validation_plan") if isinstance(plan.get("validation_plan"), dict) else {}
    required_evidence = as_list(validation.get("required_evidence"))
    if modify_repos and not required_evidence:
        findings.append(finding("validation", "high", "validation_plan.required_evidence is empty", validation, "Aggregate required evidence from acceptance mapping."))
    acceptance_task_mapping = as_list(validation.get("acceptance_task_mapping"))
    if modify_repos and required_evidence and not acceptance_task_mapping:
        findings.append(finding("validation", "high", "validation plan lacks acceptance task mapping", validation, "Map each acceptance criterion to concrete test/evidence tasks."))

    release = plan.get("release_plan") if isinstance(plan.get("release_plan"), dict) else {}
    rollback_plan = plan.get("rollback_plan") if isinstance(plan.get("rollback_plan"), dict) else {}
    release_order = [str(item) for item in as_list(release.get("release_order"))]
    rollback_order = [str(item) for item in as_list(rollback_plan.get("rollback_order"))]
    missing_release = sorted(set(modify_repos) - set(release_order))
    missing_rollback = sorted(set(modify_repos) - set(rollback_order))
    if missing_release:
        findings.append(finding("release", "high", "release_order misses modify repos", missing_release, "Include every modify repo in release_order."))
    if missing_rollback:
        findings.append(finding("rollback", "blocker", "rollback_order misses modify repos", missing_rollback, "Include every modify repo in rollback_order."))

    final_score = score(findings)
    blockers = [item for item in findings if item.get("severity") == "blocker"]
    high_or_medium = [item for item in findings if item.get("severity") in {"high", "medium"}]
    decision = "block" if blockers else "needs_revision" if high_or_medium or final_score < 85 else "pass"
    return {
        "schema": SCHEMA,
        "score": final_score,
        "decision": decision,
        "readiness_gate": {
            "implementation_allowed": decision == "pass" and final_score >= 85,
            "minimum_pass_score": 85,
            "rule": "implementation requires decision=pass, score>=85, no blocker/high/medium findings",
        },
        "findings": findings,
        "blockers": blockers,
        "modify_repos": modify_repos,
    }


def validate_review(data: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if data.get("schema") != SCHEMA:
        issues.append(f"schema must be {SCHEMA}")
    if data.get("decision") not in {"pass", "needs_revision", "block"}:
        issues.append("decision must be pass/needs_revision/block")
    if not isinstance(data.get("score"), int) or not (0 <= data.get("score", -1) <= 100):
        issues.append("score must be integer 0-100")
    gate = data.get("readiness_gate")
    if not isinstance(gate, dict) or "implementation_allowed" not in gate:
        issues.append("readiness_gate.implementation_allowed missing")
    if gate and gate.get("implementation_allowed") and data.get("decision") != "pass":
        issues.append("implementation cannot be allowed unless decision=pass")
    return not issues, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Review delivery plan execution depth")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_review = sub.add_parser("review")
    p_review.add_argument("--file", required=True)
    p_review.add_argument("--out")
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--file", required=True)
    args = parser.parse_args()

    if args.cmd == "review":
        result = review(read_json(Path(args.file)))
        if args.out:
            write_json(Path(args.out), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["decision"] == "pass" else 1
    valid, issues = validate_review(read_json(Path(args.file)))
    print(json.dumps({"schema": "codex-delivery-plan-review-validation-v1", "valid": valid, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
