from __future__ import annotations

import importlib.util
import os
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


def test_registered_project_checkout_overrides_staging_repo_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        codex_home = root / ".codex"
        checkout = root / "workspace" / "billing-service"
        checkout.mkdir(parents=True)
        (checkout / ".git").mkdir()
        registry = codex_home / "skills" / "company" / "projects.yaml"
        registry.parent.mkdir(parents=True)
        registry.write_text(
            "\n".join(
                [
                    'schema: "codex-project-registry-v1"',
                    "projects:",
                    '  - name: "billing-service"',
                    '    default_branch: "develop"',
                    "    repo:",
                    f'      local_path_hint: "{checkout}"',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        old_codex_home = os.environ.get("CODEX_HOME")
        os.environ["CODEX_HOME"] = str(codex_home)
        try:
            understanding = {
                "repository_analysis": {"project": "billing-service", "test_hints": ["pytest"]},
                "code_index": {"repo_root": str(root / "_staging" / "billing-service"), "files": [{"path": "src/service.py"}]},
            }
            technical = {
                "doc_id": "REQ-STAGING",
                "test_strategy": [{"case": "case", "evidence": ["pytest"]}],
                "acceptance_mapping": [{"acceptance_id": "AC-1", "evidence_required": ["pytest"]}],
            }
            architecture = {
                "doc_id": "REQ-STAGING",
                "repo_responsibilities": [{"repo": "billing-service", "role": "modify", "responsibility": "change service"}],
                "module_topology": [{"repo": "billing-service", "module": "src/service.py", "change_type": "modify"}],
            }
            plan = render_delivery_plan.render_from_design("REQ-STAGING", technical, architecture, understanding)
        finally:
            if old_codex_home is None:
                os.environ.pop("CODEX_HOME", None)
            else:
                os.environ["CODEX_HOME"] = old_codex_home

    task = plan["repo_tasks"][0]
    assert task["repo_path"] == str(checkout.resolve())
    assert task["base_branch"] == "develop"
    assert "_staging" not in task["repo_path"]
    assert not any("repo_path points to _staging" in item for item in plan["open_gates"])


def test_delivery_plan_excludes_unconfirmed_and_rejected_files() -> None:
    technical = {
        "doc_id": "REQ-LOC",
        "source_location_evidence": {
            "decision": "pass",
            "confirmed_anchors": [{"path": "src/views/plugIn/accidentAnalysis.vue"}],
            "rejected_candidates": [{"path": "src/views/device/replacementSettlement.vue"}],
        },
        "test_strategy": [{"case": "playback", "evidence": ["test"]}],
        "acceptance_mapping": [{"acceptance_id": "AC-1", "evidence_required": ["test"]}],
    }
    architecture = {
        "doc_id": "REQ-LOC",
        "repo_responsibilities": [{"repo": "web", "repo_path": "/workspace/web", "role": "modify", "responsibility": "playback"}],
        "module_topology": [
            {"repo": "web", "module": "src/views/plugIn/accidentAnalysis.vue", "change_type": "modify"},
            {"repo": "web", "module": "src/views/device/replacementSettlement.vue", "change_type": "modify"},
        ],
    }
    plan = render_delivery_plan.render_from_design("REQ-LOC", technical, architecture)
    assert plan["repo_tasks"][0]["allowed_files"] == ["src/views/plugIn/accidentAnalysis.vue"]
    assert any("rejected source candidates" in item for item in plan["open_gates"])


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


def test_requirement_declared_repo_missing_from_architecture_keeps_plan_incomplete() -> None:
    repo_map = {
        "multi_repo_required": True,
        "repos": [
            {"name": "sigreal-operate-platform", "relation": "owner"},
            {"name": "operate-platform-fe", "relation": "downstream"},
        ],
    }
    technical = {
        "doc_id": "REQ-FEISHU",
        "requirements_understanding_gate": {
            "design_allowed": True,
            "implementation_allowed": True,
            "business_intent": "接入飞书审批能力",
            "business_flow": ["后端创建审批实例", "前端展示审批状态"],
            "entrypoints": ["审批入口"],
            "repo_impact_map": repo_map,
        },
        "repo_impact_map": repo_map,
        "test_strategy": [{"case": "approval", "evidence": ["unit"]}],
        "acceptance_mapping": [{"acceptance_id": "AC-1", "evidence_required": ["unit"]}],
    }
    architecture = {
        "doc_id": "REQ-FEISHU",
        "repo_responsibilities": [{"repo": "sigreal-operate-platform", "repo_path": "/workspace/sigreal-operate-platform", "role": "modify", "responsibility": "backend approval"}],
        "module_topology": [{"repo": "sigreal-operate-platform", "module": "operate-provider/src/main/java/approval", "change_type": "modify"}],
    }

    plan = render_delivery_plan.render_from_design("REQ-FEISHU", technical, architecture)

    assert plan["decision"] == "needs_completion"
    assert any("operate-platform-fe: requirement-declared repository is missing" in item for item in plan["open_gates"])


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
    test_registered_project_checkout_overrides_staging_repo_path()
    test_requirement_understanding_gate_keeps_delivery_plan_incomplete()
    test_render_and_validate_file()


if __name__ == "__main__":
    run_all()
    print("PASS delivery_plan_templates tests")
