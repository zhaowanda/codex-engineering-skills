from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/core/delivery-plan-reviewer/scripts/delivery_plan_review.py"
spec = importlib.util.spec_from_file_location("delivery_plan_review", SCRIPT)
delivery_plan_review = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(delivery_plan_review)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def json_dumps(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False)


def expert_plan() -> dict:
    return {
        "schema": "codex-delivery-plan-v1",
        "doc_id": "REQ-1",
        "repo_tasks": [{
            "repo": "web-app",
            "repo_path": "/workspace/web-app",
            "role": "modify",
            "responsibility": "render export action",
            "git_preparation": {
                "required_before_edit": ["git fetch --all --prune", "git pull --ff-only", "create feature branch", "verify clean worktree"],
                "branch_naming_hint": "feature/req-1",
            },
            "tasks": [
                {"task_id": "web-read", "phase": "read", "summary": "read page and tests", "files_to_read": ["src/orders/ExportButton.tsx"], "files_to_edit": [], "implementation_notes": ["inspect current permission visibility"], "evidence_to_collect": ["read notes"], "rollback_check": "no writes", "depends_on": [], "blocking_conditions": ["file missing"], "exit_criteria": ["current behavior understood"]},
                {"task_id": "web-confirm", "phase": "confirm", "summary": "confirm permission and route scope", "files_to_read": ["src/orders/ExportButton.tsx"], "files_to_edit": [], "implementation_notes": ["confirm backend permission remains authoritative"], "evidence_to_collect": ["scope note"], "rollback_check": "scope drift updates plan", "depends_on": ["web-read"], "blocking_conditions": ["permission model unclear"], "exit_criteria": ["scope confirmed"]},
                {"task_id": "web-edit", "phase": "edit", "summary": "edit export page", "files_to_read": ["src/orders/ExportButton.tsx"], "files_to_edit": ["src/orders/ExportButton.tsx", "src/orders/ExportButton.test.tsx"], "implementation_notes": ["modify only allowed files"], "evidence_to_collect": ["git diff"], "rollback_check": "revert web commit", "depends_on": ["web-confirm"], "blocking_conditions": ["needs file outside allowed scope"], "exit_criteria": ["diff stays scoped"]},
                {"task_id": "web-test", "phase": "test", "summary": "run unit and browser tests", "files_to_read": ["src/orders/ExportButton.test.tsx"], "files_to_edit": [], "implementation_notes": ["run npm test -- ExportButton against src/orders/ExportButton.test.tsx"], "evidence_to_collect": ["test log"], "rollback_check": "failed test blocks release", "depends_on": ["web-edit"], "blocking_conditions": ["test command unavailable"], "exit_criteria": ["tests pass"]},
                {"task_id": "web-evidence", "phase": "evidence", "summary": "capture logs and screenshot evidence", "files_to_read": [], "files_to_edit": [], "implementation_notes": ["attach screenshot and logs"], "evidence_to_collect": ["frontend_acceptance"], "rollback_check": "missing evidence blocks release", "depends_on": ["web-test"], "blocking_conditions": ["screenshot cannot be captured"], "exit_criteria": ["evidence attached"]},
                {"task_id": "web-rollback", "phase": "rollback", "summary": "verify revert rollback", "files_to_read": ["src/orders/ExportButton.tsx"], "files_to_edit": [], "implementation_notes": ["validate rollback owner"], "evidence_to_collect": ["rollback note"], "rollback_check": "previous artifact can be restored", "depends_on": ["web-evidence"], "blocking_conditions": ["rollback owner unknown"], "exit_criteria": ["rollback path verified"]},
            ],
            "read_first": ["src/orders/ExportButton.tsx"],
            "allowed_files": ["src/orders/ExportButton.tsx", "src/orders/ExportButton.test.tsx"],
            "test_commands": ["npm test -- ExportButton"],
            "acceptance_evidence": [{"acceptance_id": "AC-1", "evidence_required": ["frontend_acceptance"]}],
            "risks": [{"risk": "permission visibility regression", "mitigation": "negative browser test"}],
            "rollback": [{"step": "revert web commit", "data_risk": "none"}],
        }],
        "validation_plan": {"required_evidence": ["frontend_acceptance"], "acceptance_task_mapping": [{"acceptance_id": "AC-1", "task_refs": ["web-test", "web-evidence"], "evidence_required": ["frontend_acceptance"]}]},
        "release_plan": {"release_order": ["web-app"]},
        "rollback_plan": {"rollback_order": ["web-app"]},
        "open_gates": [],
        "decision": "ready",
    }


def test_delivery_plan_reviewer_blocks_shallow_plan() -> None:
    plan = expert_plan()
    plan["open_gates"] = ["web-app: repo_path is required"]
    plan["repo_tasks"][0]["tasks"] = [{"task_id": "web-1", "summary": "change page"}]
    plan["repo_tasks"][0]["allowed_files"] = ["src"]
    plan["repo_tasks"][0]["rollback"] = []
    result = delivery_plan_review.review(plan)
    assert result["schema"] == "codex-delivery-plan-review-v1"
    assert result["decision"] == "block"
    assert result["blockers"]


def test_delivery_plan_reviewer_blocks_summary_only_tasks() -> None:
    plan = expert_plan()
    plan["repo_tasks"][0]["tasks"] = [
        {"task_id": "web-read", "phase": "read", "summary": "read"},
        {"task_id": "web-edit", "phase": "edit", "summary": "edit"},
    ]
    result = delivery_plan_review.review(plan)
    assert result["decision"] == "needs_revision"
    assert "task lacks executable detail" in json_dumps(result)


def test_delivery_plan_reviewer_flags_generic_task_notes() -> None:
    plan = expert_plan()
    plan["repo_tasks"][0]["tasks"][2]["implementation_notes"] = ["modify only allowed_files"]
    result = delivery_plan_review.review(plan)
    assert result["decision"] == "needs_revision"
    assert "task implementation notes are generic" in json_dumps(result)


def test_delivery_plan_reviewer_passes_executable_plan() -> None:
    result = delivery_plan_review.review(expert_plan())
    assert result["decision"] == "pass"
    assert result["readiness_gate"]["implementation_allowed"] is True
    valid, issues = delivery_plan_review.validate_review(result)
    assert valid, issues


def test_delivery_plan_review_cli_validate_shape() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "review.json"
        result = delivery_plan_review.review(expert_plan())
        write_json(out, result)
        loaded = delivery_plan_review.read_json(out)
        valid, issues = delivery_plan_review.validate_review(loaded)
        assert valid, issues


def run_all() -> None:
    test_delivery_plan_reviewer_blocks_shallow_plan()
    test_delivery_plan_reviewer_blocks_summary_only_tasks()
    test_delivery_plan_reviewer_flags_generic_task_notes()
    test_delivery_plan_reviewer_passes_executable_plan()
    test_delivery_plan_review_cli_validate_shape()


if __name__ == "__main__":
    run_all()
    print("PASS delivery_plan_reviewer tests")
