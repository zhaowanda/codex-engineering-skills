from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/templates/delivery-plan-templates/scripts/render_delivery_plan.py"
spec = importlib.util.spec_from_file_location("render_delivery_plan", SCRIPT)
render_delivery_plan = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(render_delivery_plan)


def test_example_plan_is_valid() -> None:
    plan = render_delivery_plan.example_plan("REQ-1")
    valid, issues = render_delivery_plan.validate(plan)
    assert valid, issues
    assert plan["decision"] == "ready"
    assert plan["repo_tasks"][0]["role"] == "modify"
    assert plan["repo_tasks"][0]["allowed_files"]


def test_missing_repo_path_keeps_plan_incomplete() -> None:
    technical = {"doc_id": "REQ-1", "test_strategy": [{"case": "case", "evidence": ["unit"]}], "acceptance_mapping": [{"acceptance_id": "AC-1", "evidence_required": ["unit"]}]}
    architecture = {
        "doc_id": "REQ-1",
        "repo_responsibilities": [{"repo": "web-app", "role": "modify", "responsibility": "change page"}],
        "module_topology": [{"repo": "web-app", "module": "src/page", "change_type": "modify"}],
    }
    plan = render_delivery_plan.render_from_design("REQ-1", technical, architecture)
    assert plan["decision"] == "needs_completion"
    assert any("repo_path is required" in item for item in plan["open_gates"])


def test_project_understanding_fills_repo_path_files_and_tests() -> None:
    understanding = {
        "repository_analysis": {
            "project": "basic-web-service",
            "entrypoint_hints": ["app/main.py"],
            "test_hints": ["tests/test_main.py"],
        },
        "dependency_surface": {"test_command_hints": ["pytest"]},
        "code_index": {
            "repo_root": "examples/synthetic-repos/basic-web-service",
            "files": [{"path": "app/main.py"}, {"path": "tests/test_main.py"}],
        },
    }
    technical = {"doc_id": "REQ-1", "test_strategy": [{"case": "case", "evidence": ["pytest"]}], "acceptance_mapping": [{"acceptance_id": "AC-1", "evidence_required": ["pytest"]}]}
    architecture = {
        "doc_id": "REQ-1",
        "repo_responsibilities": [{"repo": "basic-web-service", "role": "modify", "responsibility": "change API"}],
        "module_topology": [{"repo": "basic-web-service", "module": "app/main.py", "change_type": "modify"}],
    }
    plan = render_delivery_plan.render_from_design("REQ-1", technical, architecture, understanding)
    task = plan["repo_tasks"][0]
    assert task["repo_path"].endswith("examples/synthetic-repos/basic-web-service")
    assert "app/main.py" in task["allowed_files"]
    assert "pytest" in task["test_commands"]
    assert not any("repo_path is required" in item for item in plan["open_gates"])


def test_requirement_understanding_gate_keeps_delivery_plan_incomplete() -> None:
    gate = {
        "decision": "needs_clarification",
        "design_allowed": False,
        "implementation_allowed": False,
        "business_intent": "",
        "business_flow": [],
        "entrypoints": [],
        "blockers": [{"source": "business_flow", "message": "missing flow"}],
    }
    technical = {
        "doc_id": "REQ-AMB",
        "requirements_understanding_gate": gate,
        "test_strategy": [{"case": "case", "evidence": ["pytest"]}],
        "acceptance_mapping": [{"acceptance_id": "AC-1", "evidence_required": ["pytest"]}],
    }
    architecture = {
        "doc_id": "REQ-AMB",
        "requirements_understanding_gate": gate,
        "repo_responsibilities": [{"repo": "web-app", "repo_path": "/workspace/web-app", "role": "modify", "responsibility": "change page"}],
        "module_topology": [{"repo": "web-app", "module": "src/page.py", "change_type": "modify"}],
    }
    plan = render_delivery_plan.render_from_design("REQ-AMB", technical, architecture)
    assert plan["decision"] == "needs_completion"
    assert plan["source_design_gate"]["design_allowed"] is False
    assert any("requirements_understanding_gate" in item for item in plan["open_gates"])


def test_render_and_validate_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "delivery_plan.json"
        plan = render_delivery_plan.example_plan("REQ-1")
        render_delivery_plan.write_json(out, plan)
        loaded = render_delivery_plan.read_json(str(out))
        valid, issues = render_delivery_plan.validate(loaded)
        assert valid, issues


def run_all() -> None:
    test_example_plan_is_valid()
    test_missing_repo_path_keeps_plan_incomplete()
    test_project_understanding_fills_repo_path_files_and_tests()
    test_requirement_understanding_gate_keeps_delivery_plan_incomplete()
    test_render_and_validate_file()


if __name__ == "__main__":
    run_all()
    print("PASS delivery_plan_templates tests")
