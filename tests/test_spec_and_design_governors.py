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


spec_governor = load_module("spec_governor", ROOT / "skills/core/spec-governor/scripts/spec_governor.py")
technical_design = load_module("technical_design", ROOT / "skills/core/technical-design-governor/scripts/technical_design.py")
architecture_design = load_module("architecture_design", ROOT / "skills/core/architecture-design-governor/scripts/architecture_design.py")
project_understand = load_module("project_understand", ROOT / "skills/core/project-understanding-runner/scripts/project_understand.py")
delivery_runner = load_module("delivery_runner", ROOT / "skills/core/delivery-runner/scripts/delivery_runner.py")


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def test_technical_and_architecture_design_render_core_sections() -> None:
    spec = spec_governor.normalize("REQ-3", "Checkout display", "Buyer sees discount. AC: discount is visible before submit.")
    tech = technical_design.render(spec)
    arch = architecture_design.render(spec, tech)
    assert tech["schema"] == "codex-technical-design-v1"
    assert tech["process_flow"]
    assert len(tech["solution_options"]) == 2
    assert arch["schema"] == "codex-architecture-design-v1"
    assert arch["architecture_options"]
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
        assert status["can_implement"] is False

        spec = spec_governor.normalize("REQ-4", "Checkout display", "Buyer sees discount. AC: discount is visible.")
        write_json(root / "spec.json", spec)
        status = delivery_runner.inspect(root)
        assert status["next_stage"] == "technical_design"
        assert "technical_design.py" in status["next_command"]


def test_delivery_runner_allows_implementation_when_pre_edit_gates_pass() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name in [
            "spec",
            "technical_design",
            "architecture_design",
            "delivery_plan",
            "delivery_plan_review",
            "design_architecture_review",
            "git_worktree_evidence",
            "edit_permit",
        ]:
            write_json(root / f"{name}.json", {"decision": "pass"})
        write_json(root / "git_worktree_evidence.json", {"decision": "ready"})
        status = delivery_runner.inspect(root)
        assert status["can_implement"] is True
        assert status["next_stage"] == "implementation"


def test_delivery_runner_requires_delivery_plan_review_before_git_edit() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name in ["spec", "technical_design", "architecture_design", "delivery_plan", "design_architecture_review"]:
            write_json(root / f"{name}.json", {"decision": "pass"})
        status = delivery_runner.inspect(root)
        assert status["can_implement"] is False
        assert status["next_stage"] == "delivery_plan_review"
        assert "delivery_plan_review.py" in status["next_command"]


def run_all() -> None:
    test_spec_normalize_ready_for_design()
    test_spec_blocks_open_questions()
    test_spec_extracts_multiple_requirements_scope_risks_and_questions()
    test_spec_adds_expert_quality_fields()
    test_spec_blocks_permission_requirement_without_negative_acceptance()
    test_technical_and_architecture_design_render_core_sections()
    test_project_understanding_informs_design_and_architecture()
    test_delivery_runner_reports_next_stage()
    test_delivery_runner_allows_implementation_when_pre_edit_gates_pass()
    test_delivery_runner_requires_delivery_plan_review_before_git_edit()


if __name__ == "__main__":
    run_all()
    print("PASS spec_and_design_governors tests")
