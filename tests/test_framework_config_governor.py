from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/core/framework-config-governor/scripts/framework_config.py"
spec = importlib.util.spec_from_file_location("framework_config", SCRIPT)
framework_config = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(framework_config)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


FRAMEWORK = """
schema: codex-engineering-skills-framework-v1
paths:
  skills_root: ./skills
  artifact_root: ./.artifacts
delivery:
  default_branch_candidates:
    - main
    - master
  required_gates:
    standard_requirement:
      - doc_id
      - spec
      - technical_design
      - architecture_design
      - delivery_plan
      - git
      - edit_permit
      - implementation
      - review
      - test
      - release
    bugfix:
      - doc_id
      - reproduction
      - git
      - edit_permit
      - implementation
      - review
      - test
    hotfix:
      - doc_id
      - git
      - implementation
      - review
      - test
      - release
quality:
  design_minimum_score: 85
  design_expert_score: 90
privacy:
  pattern_file: config/private-patterns.example.yaml
"""


REGISTRY = """
schema: codex-project-registry-v1
projects:
  - name: web-app
    root: /path/to/web-app
    type: frontend
    default_branch: main
    skill: web-app
    test_strategy: npm
  - name: api-service
    root: /path/to/api-service
    type: backend
    default_branch: main
    skill: api-service
    related_projects:
      - web-app
    test_strategy: pytest
"""


def test_validate_passes_framework_and_warns_placeholder_registry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        framework = root / "config/framework.yaml"
        registry = root / "overlay/projects.yaml"
        write(framework, FRAMEWORK)
        write(registry, REGISTRY)
        result = framework_config.validate(framework, registry, root)
        assert result["decision"] == "warn"
        assert not result["blockers"]
        assert any("placeholder" in item["message"] for item in result["warnings"])


def test_validate_blocks_missing_required_gate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        framework = root / "config/framework.yaml"
        write(framework, FRAMEWORK.replace("      - architecture_design\n", ""))
        result = framework_config.validate(framework, None, root)
        assert result["decision"] == "block"
        assert any(item["source"] == "delivery.required_gates.standard_requirement" for item in result["blockers"])


def test_validate_blocks_project_root_inside_open_core() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        framework = root / "config/framework.yaml"
        registry = root / "overlay/projects.yaml"
        write(framework, FRAMEWORK)
        write(
            registry,
            """
schema: codex-project-registry-v1
projects:
  - name: web-app
    root: {root}/examples/web-app
    type: frontend
    default_branch: main
    skill: web-app
    test_strategy: npm
""".format(root=root.as_posix()),
        )
        result = framework_config.validate(framework, registry, root)
        assert result["decision"] == "block"
        assert any("open-core" in item["message"] for item in result["blockers"])


def test_validate_blocks_invalid_quality_scores() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        framework = root / "config/framework.yaml"
        write(framework, FRAMEWORK.replace("design_expert_score: 90", "design_expert_score: 70"))
        result = framework_config.validate(framework, None, root)
        assert result["decision"] == "block"
        assert any(item["source"] == "quality.design_expert_score" for item in result["blockers"])


def run_all() -> None:
    test_validate_passes_framework_and_warns_placeholder_registry()
    test_validate_blocks_missing_required_gate()
    test_validate_blocks_project_root_inside_open_core()
    test_validate_blocks_invalid_quality_scores()


if __name__ == "__main__":
    run_all()
    print("PASS framework_config_governor tests")
