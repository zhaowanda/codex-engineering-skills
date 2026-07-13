from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


traceability = load_module("traceability", ROOT / "skills/core/traceability-governor/scripts/traceability.py")
change_risk = load_module("change_risk", ROOT / "skills/core/change-risk-governor/scripts/change_risk.py")


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def test_traceability_blocks_uncovered_acceptance_and_out_of_scope_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        artifact = Path(tmp)
        write_json(artifact / "spec.json", {
            "doc_id": "REQ-1",
            "requirements": [{"id": "R-1", "summary": "export report"}],
            "acceptance_criteria": [{"id": "AC-1", "criteria": "admin exports report"}],
        })
        write_json(artifact / "delivery_plan.json", {
            "repo_tasks": [{"id": "TASK-1", "repo": "web", "role": "modify", "allowed_files": ["src/pages"], "validation": ["unit test"]}]
        })
        write_json(artifact / "test_design.json", {"test_cases": []})
        write_json(artifact / "implementation_completion_gate.json", {"changed_files": ["src/other/file.py"], "decision": "pass"})
        result = traceability.build(artifact)
        assert result["schema"] == "codex-traceability-matrix-v1"
        assert result["decision"] == "block"
        assert result["out_of_scope_files"] == ["src/other/file.py"]
        assert result["coverage"]["covered_acceptance_count"] == 0


def test_traceability_passes_when_acceptance_and_scope_are_covered() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        artifact = Path(tmp)
        write_json(artifact / "spec.json", {
            "doc_id": "REQ-1",
            "requirements": [{"id": "R-1", "summary": "export report"}],
            "acceptance_criteria": [{"id": "AC-1", "criteria": "admin exports report"}],
        })
        write_json(artifact / "technical_design.json", {"doc_id": "REQ-1"})
        write_json(artifact / "architecture_design.json", {"doc_id": "REQ-1"})
        write_json(artifact / "delivery_plan.json", {
            "repo_tasks": [{"id": "TASK-1", "repo": "web", "role": "modify", "allowed_files": ["src/pages"], "validation": ["unit test"]}]
        })
        write_json(artifact / "test_design.json", {"test_cases": [{"id": "TC-1", "acceptance_id": "AC-1"}]})
        write_json(artifact / "implementation_completion_gate.json", {"changed_files": ["src/pages/report.py"], "decision": "pass"})
        result = traceability.build(artifact)
        assert result["decision"] == "pass"
        assert result["coverage"]["covered_acceptance_count"] == 1


def test_traceability_blocks_unconfirmed_source_scope() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        artifact = Path(tmp)
        write_json(artifact / "spec.json", {"doc_id": "REQ-LOC", "acceptance_criteria": [{"id": "AC-1", "criteria": "playback works"}]})
        write_json(artifact / "technical_design.json", {
            "doc_id": "REQ-LOC",
            "source_location_evidence": {
                "decision": "pass",
                "confirmed_anchors": [{"path": "src/views/plugIn/accidentAnalysis.vue"}],
                "rejected_candidates": [{"path": "src/views/device/replacementSettlement.vue"}],
            },
        })
        write_json(artifact / "architecture_design.json", {"doc_id": "REQ-LOC"})
        write_json(artifact / "delivery_plan.json", {"repo_tasks": [{"id": "TASK-1", "repo": "web", "role": "modify", "allowed_files": ["src/views/device/replacementSettlement.vue"], "validation": ["unit test"]}]})
        write_json(artifact / "test_design.json", {"test_cases": [{"id": "TC-1", "acceptance_id": "AC-1"}]})
        result = traceability.build(artifact)
        assert result["decision"] == "block"
        assert any(item["source"] == "delivery_plan" and "confirmed" in item["message"] for item in result["blockers"])
        assert any(item["source"] == "delivery_plan" and "rejected" in item["message"] for item in result["blockers"])


def test_change_risk_marks_cross_repo_database_permission_as_high_or_critical() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        artifact = Path(tmp)
        write_json(artifact / "diff_impact.json", {
            "impact_areas": ["database", "permission", "api"],
            "evidence_required": ["sql_explain_or_migration_test"],
        })
        write_json(artifact / "delivery_plan.json", {
            "repo_tasks": [
                {"repo": "service-a", "role": "modify"},
                {"repo": "service-b", "role": "modify"},
            ]
        })
        write_json(artifact / "traceability_matrix.json", {"decision": "pass"})
        result = change_risk.classify(artifact)
        assert result["schema"] == "codex-change-risk-v1"
        assert result["decision"] == "pass"
        assert result["risk_level"] in {"high", "critical"}
        assert "release_change" in result["mandatory_gates"]
        assert "integration_test" in result["evidence_required"]


def test_change_risk_promotes_implementation_followup_evidence() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        artifact = Path(tmp)
        write_json(artifact / "implementation_completion_gate.json", {
            "decision": "pass",
            "evidence_followups": [
                {"surface": "mq_interaction", "required_by": "test-evidence-gate", "evidence": ["topic evidence"]},
                {"surface": "transaction_idempotency", "required_by": "test-evidence-gate", "evidence": ["rollback evidence"]},
                {"surface": "frontend_acceptance", "required_by": "frontend-acceptance-runner", "evidence": ["browser evidence"]},
            ],
        })
        result = change_risk.classify(artifact)
        assert result["risk_level"] in {"medium", "high", "critical"}
        assert "mq_interaction_evidence" in result["evidence_required"]
        assert "transaction_idempotency_evidence" in result["evidence_required"]
        assert "frontend_acceptance" in result["evidence_required"]


def run_all() -> None:
    test_traceability_blocks_uncovered_acceptance_and_out_of_scope_file()
    test_traceability_passes_when_acceptance_and_scope_are_covered()
    test_change_risk_marks_cross_repo_database_permission_as_high_or_critical()
    test_change_risk_promotes_implementation_followup_evidence()


if __name__ == "__main__":
    run_all()
    print("PASS traceability_and_risk tests")
