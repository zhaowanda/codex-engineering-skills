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
    write_json(root / "post_change_implementation_report.json", {"schema": "codex-post-change-implementation-report-v1", "decision": "pass", "blockers": [], "changed_files": ["src/api/orders.py"]})
    write_json(root / "write_guard_audit.json", {"decision": "ready", "blockers": []})
    write_json(root / "code_review_gate.json", {"decision": "approve", "active_blockers": [], "active_concerns": []})
    write_json(root / "test_evidence_gate.json", {"decision": "pass", "blockers": [], "warnings": []})
    write_json(root / "ci_execution_evidence.json", {"failed_commands": [], "unknown_commands": [], "executed_commands": [{"command": "pytest", "status": "passed"}]})
    write_json(
        root / "environment_promotion.json",
        {
            "decision": "pass",
            "blockers": [],
            "environments": [
                {"name": "pre", "entry_criteria": ["candidate deployed"], "exit_criteria": ["smoke passed"], "validation_evidence": ["pre smoke log"], "approver": "release-owner", "rollback_ready": True},
                {"name": "prod", "entry_criteria": ["pre passed"], "exit_criteria": ["metrics healthy"], "validation_evidence": ["prod smoke log"], "approver": "release-owner", "rollback_ready": True},
            ],
        },
    )
    write_json(root / "uat_acceptance.json", {"decision": "pass", "blockers": []})
    write_json(
        root / "release_change.json",
        {
            "decision": "pass",
            "blockers": [],
            "release_window": {"start": "2026-07-03T10:00:00+08:00", "end": "2026-07-03T11:00:00+08:00", "timezone": "Asia/Shanghai"},
            "approvers": ["release-owner"],
            "rollback_plan": ["rollback api-service"],
            "rollback_owner": "release-owner",
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
        assert "post_change_implementation_report" in result["missing_evidence"]
        assert any(item["artifact"] == "code_review_gate.json" for item in result["next_required_actions"])


def test_bind_no_go_without_post_change_report() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_release_artifacts(root)
        (root / "post_change_implementation_report.json").unlink()
        result = bind_release.bind(root)
        assert result["decision"] == "no_go"
        assert "post_change_implementation_report" in result["missing_evidence"]
        assert any(item["artifact"] == "post_change_implementation_report.json" for item in result["next_required_actions"])


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


def test_bind_no_go_when_implementation_followups_have_no_gap_summary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_release_artifacts(root)
        write_json(root / "implementation_completion_gate.json", {
            "decision": "pass",
            "blockers": [],
            "evidence_followups": [
                {"surface": "transaction_idempotency", "required_by": "test-evidence-gate", "evidence": ["rollback evidence"]}
            ],
        })
        result = bind_release.bind(root)
        assert result["decision"] == "no_go"
        assert "evidence_gap_summary" in result["missing_evidence"]


def test_bind_no_go_when_frontend_followup_lacks_frontend_acceptance() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_release_artifacts(root)
        write_json(root / "implementation_completion_gate.json", {
            "decision": "pass",
            "blockers": [],
            "evidence_followups": [
                {"surface": "frontend_acceptance", "required_by": "frontend-acceptance-runner", "evidence": ["browser evidence"]}
            ],
        })
        write_json(root / "evidence_gap_summary.json", {"decision": "pass", "missing_evidence": [], "blockers": []})
        result = bind_release.bind(root)
        assert result["decision"] == "no_go"
        assert "frontend_acceptance" in result["missing_evidence"]


def test_bind_go_when_implementation_followups_are_closed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_release_artifacts(root)
        write_json(root / "implementation_completion_gate.json", {
            "decision": "pass",
            "blockers": [],
            "evidence_followups": [
                {"surface": "frontend_acceptance", "required_by": "frontend-acceptance-runner", "evidence": ["browser evidence"]},
                {"surface": "transaction_idempotency", "required_by": "test-evidence-gate", "evidence": ["rollback evidence"]},
            ],
        })
        write_json(root / "evidence_gap_summary.json", {
            "decision": "pass",
            "missing_evidence": [],
            "blockers": [],
            "implementation_followup_requirements": [
                {"surface": "frontend_acceptance", "evidence": "frontend_acceptance"},
                {"surface": "transaction_idempotency", "evidence": "transaction_idempotency_evidence"},
            ],
        })
        write_json(root / "frontend_acceptance.json", {"decision": "pass", "pass": True, "blockers": []})
        result = bind_release.bind(root)
        assert result["decision"] == "go"
        assert len(result["implementation_evidence_followups"]) == 2


def test_bind_no_go_when_gap_summary_does_not_cover_followup_surfaces() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_release_artifacts(root)
        write_json(root / "implementation_completion_gate.json", {
            "decision": "pass",
            "blockers": [],
            "evidence_followups": [
                {"surface": "frontend_acceptance", "required_by": "frontend-acceptance-runner", "evidence": ["browser evidence"]}
            ],
        })
        write_json(root / "evidence_gap_summary.json", {"decision": "pass", "missing_evidence": [], "blockers": []})
        write_json(root / "frontend_acceptance.json", {"decision": "pass", "pass": True, "blockers": []})
        result = bind_release.bind(root)
        assert result["decision"] == "no_go"
        assert any(item["source"] == "evidence_gap_summary" and "missing_surfaces" in item for item in result["blockers"])


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


def test_bind_no_go_when_release_policy_is_template_only() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_release_artifacts(root)
        write_json(root / "environment_promotion.json", {"decision": "pass", "blockers": []})
        write_json(root / "release_change.json", {"decision": "pass", "blockers": [], "rollback_plan": ["rollback"], "post_release_checks": ["monitor"]})
        result = bind_release.bind(root)
        assert result["decision"] == "no_go"
        messages = " ".join(item["message"] for item in result["blockers"])
        assert "prod environment policy" in messages
        assert "release_window" in messages
        assert "rollback_owner" in messages


def test_bind_applies_optional_release_policy_overlay() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_release_artifacts(root)
        policy = {
            "required_environments": ["prod"],
            "environment_required_fields": ["entry_criteria", "change_ticket"],
            "release_change_required_fields": ["release_window", "approvers", "rollback_owner", "release_manager"],
            "require_prod_rollback_ready": True,
        }
        result = bind_release.bind(root, policy=policy)
        assert result["decision"] == "no_go"
        messages = " ".join(item["message"] for item in result["blockers"])
        assert "prod.change_ticket is required" in messages
        assert "release_manager is required" in messages
        assert result["release_policy"] == policy


def test_bind_go_when_optional_release_policy_is_satisfied() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_release_artifacts(root)
        release_change = json.loads((root / "release_change.json").read_text(encoding="utf-8"))
        release_change["approvers"] = [{"role": "release_owner", "name": "owner"}]
        release_change["ticket"] = {"id": "CHG-1", "url": "https://change.example/CHG-1"}
        release_change["observation_metrics"] = ["error_rate", "latency_p95"]
        write_json(root / "release_change.json", release_change)
        policy = {
            "required_environments": ["prod"],
            "environment_aliases": {"prod": ["production"]},
            "environment_required_fields": ["entry_criteria", "exit_criteria", "validation_evidence", "approver"],
            "release_change_required_fields": ["release_window", "approvers", "rollback_owner"],
            "required_approver_roles": ["release_owner"],
            "required_ticket_fields": ["id", "url"],
            "required_observation_metrics": ["error_rate", "latency_p95"],
        }
        result = bind_release.bind(root, policy=policy)
        assert result["decision"] == "go"


def test_bind_regulated_policy_requires_all_environments_and_roles() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_passing_release_artifacts(root)
        policy = {
            "required_environments": ["sit", "uat", "pre", "prod"],
            "environment_required_fields": ["entry_criteria", "exit_criteria", "validation_evidence", "approver", "change_ticket"],
            "release_change_required_fields": ["release_window", "approvers", "rollback_owner", "release_manager"],
            "required_approver_roles": ["release_owner", "qa_owner", "business_owner"],
            "required_ticket_fields": ["id", "url", "risk_level"],
            "required_observation_metrics": ["error_rate", "latency_p95", "business_success_rate"],
        }
        result = bind_release.bind(root, policy=policy)
        assert result["decision"] == "no_go"
        messages = " ".join(item["message"] for item in result["blockers"])
        assert "sit environment policy is required" in messages
        assert "required approver role missing: qa_owner" in messages
        assert "ticket.risk_level is required" in messages
        assert "observation metric required: business_success_rate" in messages


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
    test_bind_no_go_without_post_change_report()
    test_bind_no_go_when_review_gate_blocks()
    test_bind_conditional_go_with_warnings()
    test_bind_no_go_when_implementation_followups_have_no_gap_summary()
    test_bind_no_go_when_frontend_followup_lacks_frontend_acceptance()
    test_bind_go_when_implementation_followups_are_closed()
    test_bind_no_go_when_gap_summary_does_not_cover_followup_surfaces()
    test_bind_no_go_without_rollback_or_post_release_checks()
    test_bind_no_go_when_release_policy_is_template_only()
    test_bind_applies_optional_release_policy_overlay()
    test_bind_go_when_optional_release_policy_is_satisfied()
    test_bind_regulated_policy_requires_all_environments_and_roles()
    test_docs_change_uses_light_required_evidence()


if __name__ == "__main__":
    run_all()
    print("PASS release_evidence_binder tests")
