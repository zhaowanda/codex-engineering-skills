from __future__ import annotations

import importlib.util
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


build_index = load_module("build_index", ROOT / "skills/core/code-index-builder/scripts/build_index.py")
lookup_index = load_module("lookup_index", ROOT / "skills/core/code-index-lookup/scripts/lookup_index.py")
project_onboard = load_module("project_onboard", ROOT / "skills/core/project-onboard/scripts/project_onboard.py")
docs_governor = load_module("docs_governor", ROOT / "skills/core/docs-governor/scripts/docs_governor.py")
reverse_baseline = load_module("reverse_baseline", ROOT / "skills/core/project-baseline-reverser/scripts/reverse_baseline.py")


def create_repo(root: Path) -> Path:
    repo = root / "web-app"
    (repo / "src").mkdir(parents=True)
    (repo / "src/app.py").write_text(
        """
class CheckoutController:
    pass

def checkout_summary():
    return '/checkout'
""",
        encoding="utf-8",
    )
    (repo / "src/routes.js").write_text("router.get('/checkout', handler)\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests/test_checkout.py").write_text("def test_checkout(): pass\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    return repo


def test_code_index_build_and_lookup() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = create_repo(Path(tmp))
        index = build_index.build(repo, "web-app")
        assert index["schema"] == "codex-code-index-v1"
        assert index["file_count"] >= 2
        result = lookup_index.lookup(index, "checkout", 5)
        assert result["schema"] == "codex-code-index-lookup-v1"
        assert result["matches"]
        assert result["matches"][0]["score"] > 0


def test_project_onboard_writes_skill_and_manifest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        overlay = Path(tmp) / "overlay"
        result = project_onboard.onboard("web-app", "/path/to/web-app", "frontend", overlay, "main")
        assert result["schema"] == "codex-project-onboard-v1"
        assert (overlay / "skills/web-app/SKILL.md").exists()
        assert "registry_entry" in result


def test_docs_governor_init_and_validate() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "docs"
        manifest = docs_governor.init(root, "REQ-1")
        assert manifest["schema"] == "codex-docs-governor-v1"
        validation = docs_governor.validate(root, "REQ-1")
        assert validation["decision"] == "pass"


def test_project_baseline_reverser_generates_summary() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = create_repo(Path(tmp))
        result = reverse_baseline.reverse(repo, "web-app")
        assert result["schema"] == "codex-project-baseline-v1"
        assert "src" in result["top_level_directories"]
        assert result["test_hints"]
        assert result["limitations"]


def run_all() -> None:
    test_code_index_build_and_lookup()
    test_project_onboard_writes_skill_and_manifest()
    test_docs_governor_init_and_validate()
    test_project_baseline_reverser_generates_summary()


if __name__ == "__main__":
    run_all()
    print("PASS project_understanding_governors tests")
