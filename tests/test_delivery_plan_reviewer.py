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


def expert_plan() -> dict:
    return {
        "schema": "codex-delivery-plan-v1",
        "doc_id": "REQ-1",
        "repo_tasks": [{
            "repo": "web-app",
            "repo_path": "/workspace/web-app",
            "role": "modify",
            "responsibility": "render export action",
            "tasks": [
                {"task_id": "web-read", "phase": "read", "summary": "read page and tests"},
                {"task_id": "web-confirm", "phase": "confirm", "summary": "confirm permission and route scope"},
                {"task_id": "web-edit", "phase": "edit", "summary": "edit export page"},
                {"task_id": "web-test", "phase": "test", "summary": "run unit and browser tests"},
                {"task_id": "web-evidence", "phase": "evidence", "summary": "capture logs and screenshot evidence"},
                {"task_id": "web-rollback", "phase": "rollback", "summary": "verify revert rollback"},
            ],
            "read_first": ["src/orders/ExportButton.tsx"],
            "allowed_files": ["src/orders/ExportButton.tsx", "src/orders/ExportButton.test.tsx"],
            "test_commands": ["npm test -- ExportButton"],
            "acceptance_evidence": [{"acceptance_id": "AC-1", "evidence_required": ["frontend_acceptance"]}],
            "risks": [{"risk": "permission visibility regression", "mitigation": "negative browser test"}],
            "rollback": [{"step": "revert web commit", "data_risk": "none"}],
        }],
        "validation_plan": {"required_evidence": ["frontend_acceptance"]},
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
    test_delivery_plan_reviewer_passes_executable_plan()
    test_delivery_plan_review_cli_validate_shape()


if __name__ == "__main__":
    run_all()
    print("PASS delivery_plan_reviewer tests")
