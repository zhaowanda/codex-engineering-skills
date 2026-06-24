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
    test_render_and_validate_file()


if __name__ == "__main__":
    run_all()
    print("PASS delivery_plan_templates tests")
