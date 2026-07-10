from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/core/code-review-gate/scripts/review_gate.py"
spec = importlib.util.spec_from_file_location("review_gate", SCRIPT)
review_gate = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(review_gate)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_minimum_approve_artifacts(root: Path) -> None:
    write_json(root / "write_guard_audit.json", {"decision": "ready", "changed_files": ["src/service.py"]})
    write_json(root / "code_review.json", {"decision": "pass", "findings": []})
    write_json(root / "code_design_quality.json", {"decision": "pass", "findings": []})
    write_json(root / "data_security_review.json", {"decision": "pass", "findings": []})
    write_json(root / "performance_diff_review.json", {"decision": "pass", "risk_level": "low", "evidence_plan": []})
    write_json(root / "test_execution_evidence.json", {"failed_cases": [], "untested_blockers": []})
    write_json(root / "ci_execution_evidence.json", {"failed_commands": [], "unknown_commands": []})


def test_gate_approves_complete_clean_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_minimum_approve_artifacts(root)
        result = review_gate.gate(root)
        assert result["schema"] == "codex-code-review-gate-v1"
        assert result["decision"] == "approve"
        valid, issues = review_gate.validate(result)
        assert valid, issues


def test_gate_blocks_active_high_design_quality_finding() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_minimum_approve_artifacts(root)
        write_json(root / "code_design_quality.json", {
            "decision": "needs_refactor",
            "findings": [{"severity": "high", "status": "fix_required", "message": "looped IO"}],
        })
        result = review_gate.gate(root)
        assert result["decision"] == "block"
        assert result["active_blockers"]


def test_gate_requests_changes_for_missing_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_json(root / "write_guard_audit.json", {"decision": "ready", "changed_files": []})
        write_json(root / "code_review.json", {"decision": "pass", "findings": []})
        result = review_gate.gate(root)
        assert result["decision"] == "request_changes"
        assert "code_design_quality.json" in result["missing_evidence"]


def test_gate_blocks_write_guard_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_minimum_approve_artifacts(root)
        write_json(root / "write_guard_audit.json", {"decision": "blocked", "changed_files": ["src/other.py"]})
        result = review_gate.gate(root)
        assert result["decision"] == "block"
        assert any(item["source"] == "write_guard_audit" for item in result["active_blockers"])


def test_gate_requests_changes_when_implementation_followups_lack_gap_summary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_minimum_approve_artifacts(root)
        write_json(root / "implementation_completion_gate.json", {
            "decision": "pass",
            "evidence_followups": [
                {"surface": "frontend_acceptance", "required_by": "frontend-acceptance-runner"}
            ],
        })
        result = review_gate.gate(root)
        assert result["decision"] == "request_changes"
        assert "evidence_gap_summary.json" in result["missing_evidence"]
        assert any(item["source"] == "implementation_completion_gate" for item in result["active_concerns"])


def test_gate_resolves_gap_item_when_required_artifact_exists() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_minimum_approve_artifacts(root)
        write_json(root / "frontend_acceptance.json", {"decision": "pass", "pass": True})
        write_json(root / "evidence_gap_summary.json", {
            "decision": "pass",
            "missing_evidence": ["frontend_acceptance:frontend_acceptance.json"],
        })
        result = review_gate.gate(root)
        assert result["decision"] == "approve"
        assert not result["missing_evidence"]


def test_gate_requests_changes_when_gap_summary_omits_followup_surface() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_minimum_approve_artifacts(root)
        write_json(root / "implementation_completion_gate.json", {
            "decision": "pass",
            "evidence_followups": [
                {"surface": "frontend_acceptance", "required_by": "frontend-acceptance-runner"}
            ],
        })
        write_json(root / "frontend_acceptance.json", {"decision": "pass", "pass": True})
        write_json(root / "evidence_gap_summary.json", {"decision": "pass", "missing_evidence": []})
        result = review_gate.gate(root)
        assert result["decision"] == "request_changes"
        assert any(item["source"] == "evidence_gap_summary" and "missing_surfaces" in item for item in result["active_concerns"])


def run_all() -> None:
    test_gate_approves_complete_clean_evidence()
    test_gate_blocks_active_high_design_quality_finding()
    test_gate_requests_changes_for_missing_evidence()
    test_gate_blocks_write_guard_failure()
    test_gate_requests_changes_when_implementation_followups_lack_gap_summary()
    test_gate_resolves_gap_item_when_required_artifact_exists()
    test_gate_requests_changes_when_gap_summary_omits_followup_surface()


if __name__ == "__main__":
    run_all()
    print("PASS code_review_gate tests")
