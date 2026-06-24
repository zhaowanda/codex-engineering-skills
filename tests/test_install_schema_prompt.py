from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


install_skills = load_module("install_skills", ROOT / "skills/core/skill-installation-governor/scripts/install_skills.py")
artifact_schema = load_module("artifact_schema", ROOT / "skills/core/artifact-schema-governor/scripts/artifact_schema.py")
prompt_pack = load_module("prompt_pack", ROOT / "skills/core/prompt-pack-governor/scripts/prompt_pack.py")


def test_install_skills_dry_run_counts_core_and_templates() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = install_skills.install(ROOT, Path(tmp), ["core", "templates"], dry_run=True)
        assert result["schema"] == "codex-skill-installation-v1"
        assert result["decision"] == "plan"
        assert result["planned_count"] >= 40
        assert "core/spec-governor" in result["planned_skills"]


def test_default_target_uses_codex_skills_dir() -> None:
    target = install_skills.default_target().as_posix()
    assert target.endswith(".codex/skills/codex-engineering-skills") or target.endswith("skills/codex-engineering-skills")


def test_install_skills_copies_to_empty_target() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "skills"
        result = install_skills.install(ROOT, target, ["core"], dry_run=False)
        assert result["decision"] == "pass"
        assert (target / "core/spec-governor/SKILL.md").exists()


def test_artifact_schema_inventory_has_many_schemas() -> None:
    result = artifact_schema.inventory(ROOT)
    assert result["schema"] == "codex-artifact-schema-inventory-v1"
    assert result["decision"] in {"pass", "warn"}
    assert result["script_count"] >= 40
    assert result["schema_count"] >= 20


def test_prompt_pack_validates_standard_prompts() -> None:
    result = prompt_pack.validate(ROOT)
    assert result["schema"] == "codex-prompt-pack-v1"
    assert result["decision"] == "pass"
    assert result["prompt_count"] >= 5


def run_all() -> None:
    test_install_skills_dry_run_counts_core_and_templates()
    test_default_target_uses_codex_skills_dir()
    test_install_skills_copies_to_empty_target()
    test_artifact_schema_inventory_has_many_schemas()
    test_prompt_pack_validates_standard_prompts()


if __name__ == "__main__":
    run_all()
    print("PASS install_schema_prompt tests")
