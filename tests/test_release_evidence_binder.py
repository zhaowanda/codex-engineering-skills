from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/core/release-evidence-binder/scripts/bind_release.py"
spec = importlib.util.spec_from_file_location("bind_release", SCRIPT)
bind_release = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(bind_release)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_passing_release_artifacts(root: Path) -> None:
    write_json(
        root / "delivery_plan.json",
        {
            "decision": "pass",
            "rollback_order": ["revert api-service deployment"],
            "post_release_checks": ["check error rate", "check key flow"],
        },
    )
    write_json(root / "design_architecture_review.json", {"decision": "pass", "blockers": [], "warnings": []})
    write_json(root / "implementation_completion_gate.json", {"decision": "pass", "blockers": []})
    write_json(root / "write_guard_audit.json", {"decision": "ready", "blockers": []})
    write_json(root / "code_review_gate.json", {"decision": "approve", "active_blockers": [], "active_concerns": []})
    write_json(root / "test_evidence_gate.json", {"decision": "pass", "blockers": [], "warnings": []})
    write_json(root / "ci_execution_evidence.json", {"failed_commands": [], "unknown_commands": [], "executed_commands": [{"command": "pytest", "status": "passed"}]})
    write_json(root / "environment_promotion.json", {"decision": "pass", "blockers": []})
    write_json(root / "uat_acceptance.json", {"decision": "pass", "blockers": []})
    write_json(
        root / "release_change.json",
        {
            "decision": "pass",
            "blockers": [],
            "rollback_plan": ["rollback api-service"],
            "post_release_checks": ["check error rate"],
        },
    )


def test_bind_go_with_complete_clean_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_release_artifacts(root)
        result = bind_release.bind(root)
        assert result["schema"] == "codex-release-gate-v1"
        assert result["decision"] == "go"
        valid, issues = bind_release.validate(result)
        assert valid, issues


def test_bind_no_go_when_required_evidence_missing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_json(root / "delivery_plan.json", {"rollback_order": ["revert"], "post_release_checks": ["monitor"]})
        result = bind_release.bind(root)
        assert result["decision"] == "no_go"
        assert "code_review_gate" in result["missing_evidence"]


def test_bind_no_go_when_review_gate_blocks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_release_artifacts(root)
        write_json(root / "code_review_gate.json", {"decision": "block", "active_blockers": [{"message": "security issue"}]})
        result = bind_release.bind(root)
        assert result["decision"] == "no_go"
        assert any(item["source"] == "code_review_gate" for item in result["blockers"])


def test_bind_conditional_go_with_warnings() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_release_artifacts(root)
        write_json(root / "performance_diff_review.json", {"decision": "needs_evidence", "warnings": [{"message": "load test deferred"}]})
        result = bind_release.bind(root)
        assert result["decision"] == "conditional_go"
        assert result["warnings"]


def test_bind_no_go_without_rollback_or_post_release_checks() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_release_artifacts(root)
        write_json(root / "delivery_plan.json", {"decision": "pass"})
        write_json(root / "release_change.json", {"decision": "pass", "blockers": []})
        result = bind_release.bind(root)
        assert result["decision"] == "no_go"
        messages = " ".join(item["message"] for item in result["blockers"])
        assert "rollback plan" in messages
        assert "post-release checks" in messages


def test_docs_change_uses_light_required_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_json(root / "delivery_plan.json", {"decision": "pass"})
        write_json(root / "code_review_gate.json", {"decision": "approve", "active_blockers": []})
        result = bind_release.bind(root, change_type="docs")
        assert result["decision"] == "go"
        assert result["required_evidence"] == ["delivery_plan", "code_review_gate"]


def run_all() -> None:
    test_bind_go_with_complete_clean_evidence()
    test_bind_no_go_when_required_evidence_missing()
    test_bind_no_go_when_review_gate_blocks()
    test_bind_conditional_go_with_warnings()
    test_bind_no_go_without_rollback_or_post_release_checks()
    test_docs_change_uses_light_required_evidence()


if __name__ == "__main__":
    run_all()
    print("PASS release_evidence_binder tests")
