from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


spec_governor = load_module("spec_governor", ROOT / "skills/core/spec-governor/scripts/spec_governor.py")
technical_design = load_module("technical_design", ROOT / "skills/core/technical-design-governor/scripts/technical_design.py")
architecture_design = load_module("architecture_design", ROOT / "skills/core/architecture-design-governor/scripts/architecture_design.py")
project_understand = load_module("project_understand", ROOT / "skills/core/project-understanding-runner/scripts/project_understand.py")
delivery_runner = load_module("delivery_runner", ROOT / "skills/core/delivery-runner/scripts/delivery_runner.py")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_docs_repo(root: Path, doc_id: str) -> Path:
    docs_root = root / "delivery-docs"
    docs_root.mkdir()
    subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=docs_root, text=True, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=docs_root, text=True, capture_output=True, check=True)
    write_json(docs_root / "indexes" / f"{doc_id}.manifest.json", {"schema": "codex-docs-governor-v1", "doc_id": doc_id})
    subprocess.run(["git", "add", "."], cwd=docs_root, text=True, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "docs init"], cwd=docs_root, text=True, capture_output=True, check=True)
    return docs_root


def test_spec_normalize_ready_for_design() -> None:
    text = """
    Admin needs to export orders.
    Rule: only admin can export filtered results.
    AC: exported file contains order id and status.
    AC: non-admin cannot export filtered results.
    """
    spec = spec_governor.normalize("REQ-1", "Order export", text)
    assert spec["schema"] == "codex-spec-v1"
    assert spec["decision"] == "ready_for_design"
    assert spec["acceptance_criteria"]
    validation = spec_governor.validate_spec(spec)
    assert validation["decision"] == "pass"


def test_spec_blocks_open_questions() -> None:
    spec = spec_governor.normalize("REQ-2", "Unclear request", "User wants report. Which fields?")
    validation = spec_governor.validate_spec(spec)
    assert validation["decision"] == "block"
    assert any(item["source"] == "open_questions" for item in validation["blockers"])


def test_spec_extracts_multiple_requirements_scope_risks_and_questions() -> None:
    text = """
    Req: Admin exports filtered orders.
    Req: Operator sees export history.
    Rule: only admin can export filtered results.
    AC: exported file contains order id and status.
    AC: non-admin cannot see export action.
    Out of scope: scheduled exports.
    Assumption: existing order API remains available.
    Risk: large exports may be slow.
    Which columns are mandatory?
    """
    spec = spec_governor.normalize("REQ-20", "Order export", text)
    assert len(spec["requirements"]) == 2
    assert len(spec["acceptance_criteria"]) == 2
    assert spec["scope"]["out_of_scope"] == ["scheduled exports."]
    assert spec["scope"]["assumptions"] == ["existing order API remains available."]
    assert spec["risks"]
    assert spec["open_questions"]


def test_spec_adds_expert_quality_fields() -> None:
    text = """
    Goal: reduce manual export work.
    Scenario: Admin exports filtered orders from the orders page.
    Req: Admin exports filtered orders.
    Rule: only admin can export filtered results.
    AC: exported file contains order id and status.
    AC: non-admin cannot see export action.
    """
    spec = spec_governor.normalize("REQ-21", "Order export", text)
    assert spec["personas"]
    assert spec["user_scenarios"]
    assert spec["business_objectives"]
    assert spec["negative_acceptance_criteria"]
    assert any(item["area"] == "permission" for item in spec["impact_surface"])
    validation = spec_governor.validate_spec(spec)
    assert validation["decision"] == "pass"


def test_spec_handles_one_line_request_with_inferred_acceptance() -> None:
    spec = spec_governor.normalize("REQ-ONE", "Checkout copy", "Change checkout button text to Pay now.")
    assert spec["lane"] == "small_change"
    assert spec["requirements"][0]["summary"] == "Change checkout button text to Pay now."
    assert spec["acceptance_criteria"][0]["source_evidence"] == "inferred from first line"
    assert spec["source"]["line_count"] == 1
    validation = spec_governor.validate_spec(spec)
    assert validation["decision"] == "pass"
    assert validation["quality_level"] == "usable"
    assert any(item["source"] == "acceptance_criteria" for item in validation["warnings"])


def test_spec_handles_long_prd_without_collapsing_traceability() -> None:
    lines = [
        "Goal: reduce manual operations.",
        "Req: Admin exports filtered orders.",
        "Req: Operator reviews export history.",
        "Req: Customer service audits export failures.",
        "Rule: only admin can export filtered results.",
        "Rule: operators can view export history only.",
        "AC: exported file contains order id and status.",
        "AC: non-admin cannot export filtered results.",
        "Risk: large exports may be slow.",
        "Out of scope: scheduled exports.",
    ]
    lines.extend(f"Detail {idx}: preserve existing report behavior." for idx in range(1, 28))
    spec = spec_governor.normalize("REQ-LONG", "Long order export PRD", "\n".join(lines))
    assert spec["lane"] == "large_prd"
    assert len(spec["requirements"]) == 3
    assert len(spec["business_rules"]) >= 2
    assert len(spec["source_trace"]) > 30
    assert spec["risks"]
    assert spec["scope"]["out_of_scope"] == ["scheduled exports."]


def test_spec_exposes_complex_multi_impact_requirements() -> None:
    text = """
    Goal: reduce failed payment support work.
    Scenario: Admin reviews payment export failures from the dashboard page.
    Req: Add an API endpoint for payment export failures.
    Req: Add a dashboard page for admins.
    Req: Add a database migration for failure reason and retry count.
    Rule: only admin role can access payment failure data.
    Rule: export must finish within the existing latency budget.
    AC: API returns payment failure rows.
    AC: dashboard page shows retry count.
    AC: non-admin cannot view payment failure data.
    AC: export latency remains within the performance budget.
    Risk: payment data may contain sensitive fields.
    """
    spec = spec_governor.normalize("REQ-COMPLEX", "Payment failure dashboard", text)
    impacts = {item["area"] for item in spec["impact_surface"]}
    assert {"api", "ui", "data", "permission", "performance", "security"}.issubset(impacts)
    assert spec["data_classification"]["requires_security_review"] is True
    assert spec["permission_scope"]["negative_cases_required"] is True
    assert spec["negative_acceptance_criteria"]
    assert {"payment", "dashboard"}.issubset({item["name"] for item in spec["business_objects"]})
    assert {"retry_count", "failure_reason"}.issubset({item["name"] for item in spec["data_fields"]})
    assert {"view"}.issubset({item["name"] for item in spec["operations"]})
    assert {item["area"] for item in spec["implicit_constraints"]} >= {"permission", "data", "api", "performance", "security"}


def test_spec_blocks_permission_requirement_without_negative_acceptance() -> None:
    text = """
    Req: Admin exports filtered orders.
    Rule: only admin can export filtered results.
    AC: exported file contains order id and status.
    """
    spec = spec_governor.normalize("REQ-22", "Order export", text)
    validation = spec_governor.validate_spec(spec)
    assert validation["decision"] == "block"
    assert any(item["source"] == "negative_acceptance_criteria" for item in validation["blockers"])


def test_spec_blocks_conflicting_permission_rules() -> None:
    text = """
    Req: Export order report.
    Rule: only admin can export order report.
    Rule: operator can export order report.
    AC: admin can export order report.
    """
    spec = spec_governor.normalize("REQ-CONFLICT", "Order export", text)
    validation = spec_governor.validate_spec(spec)
    assert spec["rule_conflicts"]
    assert validation["decision"] == "block"
    assert any(item["source"] == "rule_conflicts" for item in validation["blockers"])


def test_spec_extracts_state_transitions() -> None:
    spec = spec_governor.normalize("REQ-STATE", "Refund state", "Req: change refund status from pending to completed.\nAC: status is completed.")
    assert spec["state_transitions"]
    assert spec["state_transitions"][0]["from"] == "pending"
    assert "completed" in spec["state_transitions"][0]["to"]


def test_technical_and_architecture_design_render_core_sections() -> None:
    spec = spec_governor.normalize("REQ-3", "Checkout display", "Buyer sees discount. AC: discount is visible before submit.")
    tech = technical_design.render(spec)
    arch = architecture_design.render(spec, tech)
    assert tech["schema"] == "codex-technical-design-v1"
    assert tech["process_flow"]
    assert len(tech["solution_options"]) == 2
    assert tech["selected_solution"]["rejected_alternative_reasoning"]
    assert arch["schema"] == "codex-architecture-design-v1"
    assert arch["architecture_options"]
    assert arch["selected_architecture"]["rejected_alternative_reasoning"]
    assert arch["repo_responsibilities"][0]["role"] == "modify"


def test_project_understanding_informs_design_and_architecture() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        understanding_dir = Path(tmp) / "understanding"
        project_understand.run(ROOT / "examples/synthetic-repos/basic-web-service", "basic-web-service", understanding_dir)
        spec = spec_governor.normalize("REQ-30", "Order export", "Admin exports orders. AC: exported file contains order id.")
        tech = technical_design.render(spec, technical_design.load_project_understanding(understanding_dir))
        arch = architecture_design.render(spec, tech, architecture_design.load_project_understanding(understanding_dir))
        assert tech["project_context"]["project"] == "basic-web-service"
        assert "app/main.py" in tech["project_context"]["read_first"]
        assert tech["module_decomposition"][0]["module"] != "target module to be confirmed"
        assert arch["repo_responsibilities"][0]["repo"] == "basic-web-service"
        assert arch["repo_responsibilities"][0]["repo_path"].endswith("examples/synthetic-repos/basic-web-service")


def test_delivery_runner_reports_next_stage() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        status = delivery_runner.inspect(root)
        assert status["next_stage"] == "spec"
        assert status["next_action_type"] == "fix_blocker"
        assert status["primary_next_action"]["action_type"] == "fix_blocker"
        assert status["can_implement"] is False

        spec = spec_governor.normalize("REQ-4", "Checkout display", "Buyer sees discount. AC: discount is visible.")
        write_json(root / "spec.json", spec)
        status = delivery_runner.inspect(root)
        assert status["next_stage"] == "technical_design"
        assert "technical_design.py" in status["next_command"]


def test_delivery_runner_allows_implementation_when_pre_edit_gates_pass() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = make_docs_repo(root, "REQ-1")
        for name in [
            "spec",
            "technical_design",
            "architecture_design",
            "test_design",
            "test_data_plan",
            "docs_quality",
            "git_worktree_evidence",
            "edit_permit",
        ]:
            write_json(root / f"{name}.json", {"decision": "pass"})
        write_json(root / "delivery_plan.json", {"decision": "pass", "doc_id": "REQ-1"})
        write_json(root / "delivery_plan_review.json", {"decision": "pass", "readiness_gate": {"implementation_allowed": True}})
        write_json(root / "design_architecture_review.json", {"decision": "pass", "readiness_gate": {"implementation_allowed": True}})
        write_json(root / "git_worktree_evidence.json", {"decision": "ready", "fetched": True, "base_updated": True})
        write_json(root / "auto_run_summary.json", {
            "doc_id": "REQ-1",
            "docs_readiness": {
                "decision": "pass",
                "docs_root": str(docs_root),
                "manifest": str(docs_root / "indexes/REQ-1.manifest.json"),
            },
        })
        status = delivery_runner.inspect(root)
        assert status["can_implement"] is True
        assert status["next_stage"] == "implementation"
        assert status["next_action_type"] == "ready_to_implement"


def test_delivery_runner_requires_delivery_plan_review_before_git_edit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name in ["spec", "technical_design", "architecture_design", "delivery_plan", "design_architecture_review"]:
            write_json(root / f"{name}.json", {"decision": "pass"})
        status = delivery_runner.inspect(root)
        assert status["can_implement"] is False
        assert status["next_stage"] == "test_design"
        assert status["next_action_type"] == "fix_blocker"
        assert "test_design.py" in status["next_command"]


def test_delivery_runner_blocks_when_profile_gate_readiness_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = make_docs_repo(root, "REQ-1")
        for name in ["spec", "technical_design", "architecture_design", "test_design", "docs_quality", "delivery_plan", "git_worktree_evidence", "edit_permit"]:
            write_json(root / f"{name}.json", {"decision": "pass"})
        write_json(root / "delivery_plan.json", {"decision": "pass", "doc_id": "REQ-1"})
        write_json(root / "git_worktree_evidence.json", {"decision": "ready", "fetched": True, "base_updated": True})
        write_json(root / "auto_run_summary.json", {
            "doc_id": "REQ-1",
            "docs_readiness": {
                "decision": "pass",
                "docs_root": str(docs_root),
                "manifest": str(docs_root / "indexes/REQ-1.manifest.json"),
            },
        })
        write_json(root / "delivery_plan_review.json", {"decision": "pass", "readiness_gate": {"implementation_allowed": False}})
        write_json(root / "design_architecture_review.json", {"decision": "pass", "readiness_gate": {"implementation_allowed": True}})
        status = delivery_runner.inspect(root, profile_name="small_feature")
        assert status["can_implement"] is False
        assert any(item["source"] == "profile_gate.delivery_plan_review.json" for item in status["blockers"])


def test_delivery_runner_requires_docs_and_fresh_git_before_implementation() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name in ["spec", "technical_design", "architecture_design", "test_design", "docs_quality", "edit_permit"]:
            write_json(root / f"{name}.json", {"decision": "pass"})
        write_json(root / "delivery_plan.json", {"decision": "pass", "doc_id": "REQ-1"})
        write_json(root / "delivery_plan_review.json", {"decision": "pass", "readiness_gate": {"implementation_allowed": True}})
        write_json(root / "design_architecture_review.json", {"decision": "pass", "readiness_gate": {"implementation_allowed": True}})
        write_json(root / "git_worktree_evidence.json", {"decision": "ready"})
        status = delivery_runner.inspect(root)
        assert status["can_implement"] is False
        assert any(item["source"] == "docs_root" for item in status["blockers"])
        assert any("fetch evidence is missing" in item["message"] for item in status["blockers"])
        assert any("pull --ff-only evidence is missing" in item["message"] for item in status["blockers"])


def test_delivery_runner_blocks_when_docs_quality_not_pass() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        docs_root = make_docs_repo(root, "REQ-1")
        for name in ["spec", "technical_design", "architecture_design", "test_design", "delivery_plan", "git_worktree_evidence", "edit_permit"]:
            write_json(root / f"{name}.json", {"decision": "pass"})
        write_json(root / "docs_quality.json", {"decision": "warn", "warnings": [{"source": "depth"}]})
        write_json(root / "delivery_plan.json", {"decision": "pass", "doc_id": "REQ-1"})
        write_json(root / "delivery_plan_review.json", {"decision": "pass", "readiness_gate": {"implementation_allowed": True}})
        write_json(root / "design_architecture_review.json", {"decision": "pass", "readiness_gate": {"implementation_allowed": True}})
        write_json(root / "git_worktree_evidence.json", {"decision": "ready", "fetched": True, "base_updated": True})
        write_json(root / "auto_run_summary.json", {
            "doc_id": "REQ-1",
            "docs_readiness": {
                "decision": "pass",
                "docs_root": str(docs_root),
                "manifest": str(docs_root / "indexes/REQ-1.manifest.json"),
            },
        })
        status = delivery_runner.inspect(root)
        assert status["can_implement"] is False
        assert any(item["source"] == "docs_quality" for item in status["blockers"])


def run_all() -> None:
    test_spec_normalize_ready_for_design()
    test_spec_blocks_open_questions()
    test_spec_extracts_multiple_requirements_scope_risks_and_questions()
    test_spec_adds_expert_quality_fields()
    test_spec_handles_one_line_request_with_inferred_acceptance()
    test_spec_handles_long_prd_without_collapsing_traceability()
    test_spec_exposes_complex_multi_impact_requirements()
    test_spec_blocks_permission_requirement_without_negative_acceptance()
    test_spec_blocks_conflicting_permission_rules()
    test_spec_extracts_state_transitions()
    test_technical_and_architecture_design_render_core_sections()
    test_project_understanding_informs_design_and_architecture()
    test_delivery_runner_reports_next_stage()
    test_delivery_runner_allows_implementation_when_pre_edit_gates_pass()
    test_delivery_runner_requires_delivery_plan_review_before_git_edit()
    test_delivery_runner_blocks_when_profile_gate_readiness_fails()
    test_delivery_runner_requires_docs_and_fresh_git_before_implementation()
    test_delivery_runner_blocks_when_docs_quality_not_pass()


if __name__ == "__main__":
    run_all()
    print("PASS spec_and_design_governors tests")
