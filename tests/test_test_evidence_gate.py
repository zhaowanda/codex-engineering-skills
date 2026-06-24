from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/core/test-evidence-gate/scripts/test_evidence_gate.py"
spec = importlib.util.spec_from_file_location("test_evidence_gate", SCRIPT)
test_evidence_gate = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(test_evidence_gate)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_passing_artifacts(root: Path) -> None:
    write_json(
        root / "test_execution_evidence.json",
        {
            "executed_cases": [{"name": "create order succeeds", "status": "passed"}],
            "failed_cases": [],
            "untested_blockers": [],
        },
    )
    write_json(
        root / "ci_execution_evidence.json",
        {
            "executed_commands": [{"command": "pytest tests/test_order.py", "status": "passed"}],
            "failed_commands": [],
            "unknown_commands": [],
            "manual_review_required": [],
        },
    )


def test_gate_passes_with_real_tests_and_clean_ci() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_artifacts(root)
        result = test_evidence_gate.evaluate(root)
        assert result["schema"] == "codex-test-evidence-gate-v1"
        assert result["decision"] == "pass"
        valid, issues = test_evidence_gate.validate(result)
        assert valid, issues


def test_gate_blocks_missing_test_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_json(root / "ci_execution_evidence.json", {"executed_commands": [{"command": "pytest", "status": "passed"}]})
        result = test_evidence_gate.evaluate(root)
        assert result["decision"] == "block"
        assert any(item["source"] == "test_execution_evidence" for item in result["blockers"])


def test_gate_blocks_failed_cases() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_artifacts(root)
        write_json(
            root / "test_execution_evidence.json",
            {
                "executed_cases": [{"name": "refund rejects invalid amount", "status": "failed"}],
                "failed_cases": [{"name": "refund rejects invalid amount"}],
                "untested_blockers": [],
            },
        )
        result = test_evidence_gate.evaluate(root)
        assert result["decision"] == "block"
        assert any("failed test cases" in item["message"] for item in result["blockers"])


def test_gate_blocks_ci_failed_unknown_or_plan_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_artifacts(root)
        write_json(
            root / "ci_execution_evidence.json",
            {
                "mode": "plan",
                "failed_commands": [{"command": "npm test"}],
                "unknown_commands": [{"command": "npm run lint"}],
            },
        )
        result = test_evidence_gate.evaluate(root)
        assert result["decision"] == "block"
        messages = " ".join(item["message"] for item in result["blockers"])
        assert "plan-only" in messages
        assert "failed CI commands" in messages
        assert "unknown CI command" in messages


def test_gate_blocks_required_frontend_missing_or_failing() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_artifacts(root)
        missing = test_evidence_gate.evaluate(root, require_frontend=True)
        assert missing["decision"] == "block"

        write_json(root / "frontend_acceptance.json", {"pass": False, "console_errors": ["error"]})
        failing = test_evidence_gate.evaluate(root, require_frontend=True)
        assert failing["decision"] == "block"
        assert any(item["source"] == "frontend_acceptance" for item in failing["blockers"])


def test_gate_passes_required_frontend_with_clean_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_artifacts(root)
        write_json(root / "frontend_acceptance.json", {"pass": True, "console_errors": [], "failed_requests": []})
        result = test_evidence_gate.evaluate(root, require_frontend=True)
        assert result["decision"] == "pass"
        assert result["evidence_summary"]["frontend_required"] is True


def run_all() -> None:
    test_gate_passes_with_real_tests_and_clean_ci()
    test_gate_blocks_missing_test_evidence()
    test_gate_blocks_failed_cases()
    test_gate_blocks_ci_failed_unknown_or_plan_only()
    test_gate_blocks_required_frontend_missing_or_failing()
    test_gate_passes_required_frontend_with_clean_evidence()


if __name__ == "__main__":
    run_all()
    print("PASS test_evidence_gate tests")
