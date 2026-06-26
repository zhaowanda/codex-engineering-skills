from __future__ import annotations

import importlib.util
import re
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

B_LEVEL_UPGRADE_SKILLS = [
    "skills/core/api-surface-extractor/SKILL.md",
    "skills/core/baseline-quality-governor/SKILL.md",
    "skills/core/change-risk-governor/SKILL.md",
    "skills/core/code-index-builder/SKILL.md",
    "skills/core/code-index-lookup/SKILL.md",
    "skills/core/config-surface-extractor/SKILL.md",
    "skills/core/dependency-surface-analyzer/SKILL.md",
    "skills/core/diff-impact-analyzer/SKILL.md",
    "skills/core/evidence-auto-collector/SKILL.md",
    "skills/core/git-history-miner/SKILL.md",
    "skills/core/human-doc-reviewer/SKILL.md",
    "skills/templates/ci-templates/SKILL.md",
]

FINAL_A_LEVEL_SKILLS = [
    "skills/core/artifact-schema-governor/SKILL.md",
    "skills/core/dependency-license-governor/SKILL.md",
    "skills/core/deprecation-governor/SKILL.md",
    "skills/core/issue-pr-governor/SKILL.md",
    "skills/core/post-release-observer/SKILL.md",
    "skills/core/prompt-pack-governor/SKILL.md",
    "skills/core/requirement-document-ingestor/SKILL.md",
    "skills/core/skill-installation-governor/SKILL.md",
]


def score_skill_doc(text: str, script_count: int, schema_count: int, test_refs: int) -> int:
    words = len(re.findall(r"\w+", text))
    score = 50
    score += min(15, script_count * 8)
    score += min(12, schema_count * 3)
    score += 8 if "## Rules" in text else 0
    score += 8 if "## Output" in text else 0
    score += 5 if "## Position" in text else 0
    score += min(10, test_refs * 5)
    score += 5 if "```bash" in text else 0
    score += 5 if words >= 180 else 0
    return min(score, 100)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


skill_health = load_module("skill_health", ROOT / "skills/core/skill-health/scripts/skill_health.py")
overlay_health = load_module("overlay_health", ROOT / "skills/core/overlay-health/scripts/overlay_health.py")
human_doc_review = load_module("human_doc_review", ROOT / "skills/core/human-doc-reviewer/scripts/human_doc_review.py")
forward_test = load_module("forward_test", ROOT / "skills/core/forward-test-runner/scripts/forward_test.py")


def test_skill_health_runs_on_repo() -> None:
    result = skill_health.check(ROOT)
    assert result["schema"] == "codex-skill-health-v1"
    assert result["decision"] in {"pass", "warn"}
    assert result["skill_count"] > 10
    assert not [item for item in result["warnings"] if item["message"] == "skill is not listed in README"]


def test_root_skill_health_wrapper_exists_for_readme_command() -> None:
    wrapper = ROOT / "scripts/skill_health.py"
    assert wrapper.exists()
    assert "skills/core/skill-health/scripts/skill_health.py" in wrapper.read_text(encoding="utf-8")


def test_all_skill_docs_declare_output_section() -> None:
    offenders = []
    for path in sorted((ROOT / "skills").glob("*/*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        if not re.search(r"^## Output$", text, flags=re.MULTILINE):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders


def test_readme_uses_current_validation_commands() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "python3 -m pytest -q" in readme
    assert "python3 -m compileall -q scripts skills tests" in readme
    assert "python3 scripts/skill_health.py --root ." in readme


def test_previously_b_level_skill_docs_have_operational_guidance() -> None:
    offenders = []
    required_sections = ["## Position", "## Rules", "## Output"]
    for rel in B_LEVEL_UPGRADE_SKILLS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        missing = [section for section in required_sections if section not in text]
        if missing or len(re.findall(r"^- ", text, flags=re.MULTILINE)) < 5:
            offenders.append({"path": rel, "missing": missing})
    assert not offenders


def test_final_target_skill_docs_have_operational_guidance() -> None:
    offenders = []
    required_sections = ["## Position", "## Rules", "## Output"]
    for rel in FINAL_A_LEVEL_SKILLS:
        text = (ROOT / rel).read_text(encoding="utf-8")
        missing = [section for section in required_sections if section not in text]
        if missing or len(re.findall(r"^- ", text, flags=re.MULTILINE)) < 5:
            offenders.append({"path": rel, "missing": missing})
    assert not offenders


def test_skill_quality_distribution_is_all_a_level() -> None:
    tests_text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "tests").glob("test_*.py"))
    levels: dict[str, list[str]] = {"A": [], "B+": [], "B": [], "C+": [], "C": []}
    for path in sorted((ROOT / "skills").glob("*/*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        script_text = "\n".join(
            script.read_text(encoding="utf-8", errors="ignore") for script in (path.parent / "scripts").glob("*.py")
        )
        schemas = set(re.findall(r"codex-[a-z0-9-]+-v\d+", text + "\n" + script_text))
        name = path.parent.name
        test_refs = sum(1 for pattern in [name, name.replace("-", "_")] if pattern in tests_text)
        score = score_skill_doc(text, len(list((path.parent / "scripts").glob("*.py"))), len(schemas), test_refs)
        level = "A" if score >= 90 else "B+" if score >= 82 else "B" if score >= 75 else "C+" if score >= 68 else "C"
        levels[level].append(path.relative_to(ROOT).as_posix())
    assert len(levels["A"]) == 71
    assert levels["B+"] == []
    assert levels["B"] == []
    assert levels["C+"] == []
    assert levels["C"] == []


def test_overlay_health_blocks_missing_registry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = overlay_health.check(Path(tmp))
        assert result["decision"] == "block"
        assert result["blockers"]


def test_human_doc_review_detects_local_path() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "doc.md"
        local_path = "/" + "Users/example/private"
        doc.write_text(f"Scope\nDecision\nOptions\nRisk\nEvidence\nRollback\n{local_path}\n", encoding="utf-8")
        result = human_doc_review.review(doc)
        assert result["decision"] == "block"
        assert any(item["source"] == "local_path" for item in result["blockers"])


def test_human_doc_review_warns_thin_doc() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        doc = Path(tmp) / "doc.md"
        doc.write_text("short\n", encoding="utf-8")
        result = human_doc_review.review(doc)
        assert result["decision"] == "warn"
        assert result["warnings"]


def test_forward_test_runner_passes_synthetic_case() -> None:
    result = forward_test.run(ROOT)
    assert result["schema"] == "codex-forward-test-run-v1"
    assert result["decision"] == "pass"
    assert result["cases"][0]["passed"] is True


def run_all() -> None:
    test_skill_health_runs_on_repo()
    test_root_skill_health_wrapper_exists_for_readme_command()
    test_all_skill_docs_declare_output_section()
    test_readme_uses_current_validation_commands()
    test_previously_b_level_skill_docs_have_operational_guidance()
    test_final_target_skill_docs_have_operational_guidance()
    test_skill_quality_distribution_is_all_a_level()
    test_overlay_health_blocks_missing_registry()
    test_human_doc_review_detects_local_path()
    test_human_doc_review_warns_thin_doc()
    test_forward_test_runner_passes_synthetic_case()


if __name__ == "__main__":
    run_all()
    print("PASS health_and_forward tests")
