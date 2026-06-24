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


release_package = load_module("release_package", ROOT / "skills/core/release-package-governor/scripts/release_package.py")
deprecation = load_module("deprecation", ROOT / "skills/core/deprecation-governor/scripts/deprecation.py")
roadmap = load_module("roadmap", ROOT / "skills/core/roadmap-governor/scripts/roadmap.py")
docs_readability = load_module("docs_readability", ROOT / "skills/core/docs-readability-governor/scripts/docs_readability.py")
prompt_effectiveness = load_module("prompt_effectiveness", ROOT / "skills/core/prompt-effectiveness-governor/scripts/prompt_effectiveness.py")


def test_release_package_passes_repo() -> None:
    result = release_package.review(ROOT)
    assert result["schema"] == "codex-release-package-v1"
    assert result["decision"] == "pass"
    assert result["manifest"]["dry_run"] is True


def test_release_package_blocks_missing_changelog() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "README.md").write_text("# x\n", encoding="utf-8")
        (root / "LICENSE").write_text("MIT\n", encoding="utf-8")
        (root / "CONTRIBUTING.md").write_text("contrib\n", encoding="utf-8")
        (root / "SECURITY.md").write_text("security\n", encoding="utf-8")
        (root / "pyproject.toml").write_text("[project]\nversion = '1.0.0'\n", encoding="utf-8")
        for name in ["docs", "skills", "prompts", "examples", "tests", "scripts", ".github/workflows"]:
            (root / name).mkdir(parents=True, exist_ok=True)
        result = release_package.review(root)
        assert result["decision"] == "block"


def test_deprecation_policy_passes_repo() -> None:
    result = deprecation.review(ROOT)
    assert result["schema"] == "codex-deprecation-review-v1"
    assert result["decision"] == "pass"


def test_roadmap_governor_passes_repo() -> None:
    result = roadmap.review(ROOT)
    assert result["schema"] == "codex-roadmap-review-v1"
    assert result["decision"] == "pass"


def test_docs_readability_governor_passes_repo() -> None:
    result = docs_readability.review(ROOT)
    assert result["schema"] == "codex-docs-readability-v1"
    assert result["decision"] == "pass"


def test_prompt_effectiveness_governor_passes_repo() -> None:
    result = prompt_effectiveness.review(ROOT)
    assert result["schema"] == "codex-prompt-effectiveness-v1"
    assert result["decision"] == "pass"
    assert result["prompt_count"] == 6


def run_all() -> None:
    test_release_package_passes_repo()
    test_release_package_blocks_missing_changelog()
    test_deprecation_policy_passes_repo()
    test_roadmap_governor_passes_repo()
    test_docs_readability_governor_passes_repo()
    test_prompt_effectiveness_governor_passes_repo()


if __name__ == "__main__":
    run_all()
    print("PASS release_evolution_governors tests")
