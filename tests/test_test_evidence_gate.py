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


def write_data_linked_artifacts(root: Path) -> None:
    write_json(
        root / "test_design.json",
        {
            "schema": "codex-test-design-v1",
            "decision": "pass",
            "test_cases": [
                {
                    "id": "TC-1",
                    "title": "create order succeeds",
                    "test_data_refs": ["TD-TC-1"],
                    "cleanup_expectations": ["delete TD-TC-1"],
                }
            ],
        },
    )
    write_json(
        root / "test_data_plan.json",
        {
            "schema": "codex-test-data-plan-v1",
            "decision": "pass",
            "datasets": [{"id": "TD-TC-1", "case_ids": ["TC-1"]}],
            "case_data_matrix": [{"case_id": "TC-1", "dataset_ids": ["TD-TC-1"]}],
        },
    )
    write_json(
        root / "test_execution_evidence.json",
        {
            "executed_cases": [{"id": "TC-1", "name": "create order succeeds", "status": "passed", "dataset_ids": ["TD-TC-1"]}],
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


def test_gate_passes_with_test_data_plan_and_dataset_linkage() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_data_linked_artifacts(root)
        result = test_evidence_gate.evaluate(root)
        assert result["decision"] == "pass"
        assert result["evidence_summary"]["test_data_plan_present"] is True
        assert result["evidence_summary"]["required_test_data_ref_count"] == 1


def test_gate_blocks_missing_must_run_case_execution() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_data_linked_artifacts(root)
        design = json.loads((root / "test_design.json").read_text(encoding="utf-8"))
        design["test_cases"].append(
            {
                "id": "TC-2",
                "title": "refund rejects invalid amount",
                "type": "functional",
                "execution_required": "must_run",
                "steps": ["call refund API"],
                "expected_result": "rejected",
                "evidence_required": ["api test"],
            }
        )
        write_json(root / "test_design.json", design)
        result = test_evidence_gate.evaluate(root)
        assert result["decision"] == "block"
        assert any(item["message"] == "must-run test cases were not executed" and item["missing_case_ids"] == ["TC-2"] for item in result["blockers"])
        assert result["evidence_summary"]["must_run_case_count"] == 1


def test_gate_blocks_blocked_test_design_even_with_execution_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_artifacts(root)
        gate = {"decision": "needs_clarification", "design_allowed": False, "implementation_allowed": False}
        write_json(
            root / "test_design.json",
            {
                "schema": "codex-test-design-v1",
                "decision": "block",
                "requirements_understanding_gate": gate,
                "test_cases": [{"id": "TC-1", "title": "blocked design", "execution_required": "must_run"}],
            },
        )
        write_json(
            root / "test_execution_evidence.json",
            {"executed_cases": [{"id": "TC-1", "name": "blocked design", "status": "passed"}], "failed_cases": [], "untested_blockers": []},
        )
        result = test_evidence_gate.evaluate(root)
        assert result["decision"] == "block"
        sources = {item["source"] for item in result["blockers"]}
        assert {"test_design", "requirements_understanding_gate"}.issubset(sources)


def test_gate_blocks_blocked_test_data_plan_without_required_refs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_artifacts(root)
        write_json(root / "test_data_plan.json", {"schema": "codex-test-data-plan-v1", "decision": "block", "blockers": [{"message": "blocked"}]})
        result = test_evidence_gate.evaluate(root)
        assert result["decision"] == "block"
        assert any(item["source"] == "test_data_plan" and "decision is block" in item["message"] for item in result["blockers"])


def test_gate_blocks_test_data_refs_without_plan() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_data_linked_artifacts(root)
        (root / "test_data_plan.json").unlink()
        result = test_evidence_gate.evaluate(root)
        assert result["decision"] == "block"
        assert any(item["source"] == "test_data_plan" for item in result["blockers"])


def test_gate_blocks_missing_dataset_linkage_in_execution() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_data_linked_artifacts(root)
        write_json(
            root / "test_execution_evidence.json",
            {"executed_cases": [{"id": "TC-1", "name": "create order succeeds", "status": "passed"}], "failed_cases": [], "untested_blockers": []},
        )
        result = test_evidence_gate.evaluate(root)
        assert result["decision"] == "block"
        assert any(item["message"] == "executed case is missing dataset linkage" for item in result["blockers"])


def test_gate_blocks_plan_missing_required_dataset_ref() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_data_linked_artifacts(root)
        write_json(
            root / "test_data_plan.json",
            {"schema": "codex-test-data-plan-v1", "decision": "pass", "datasets": [{"id": "TD-OTHER", "case_ids": ["TC-1"]}]},
        )
        result = test_evidence_gate.evaluate(root)
        assert result["decision"] == "block"
        assert any(item["message"] == "test data refs missing from plan" for item in result["blockers"])


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
    test_gate_passes_with_test_data_plan_and_dataset_linkage()
    test_gate_blocks_blocked_test_design_even_with_execution_evidence()
    test_gate_blocks_blocked_test_data_plan_without_required_refs()
    test_gate_blocks_test_data_refs_without_plan()
    test_gate_blocks_missing_dataset_linkage_in_execution()
    test_gate_blocks_plan_missing_required_dataset_ref()
    test_gate_blocks_missing_test_evidence()
    test_gate_blocks_failed_cases()
    test_gate_blocks_ci_failed_unknown_or_plan_only()
    test_gate_blocks_required_frontend_missing_or_failing()
    test_gate_passes_required_frontend_with_clean_evidence()


if __name__ == "__main__":
    run_all()
    print("PASS test_evidence_gate tests")
