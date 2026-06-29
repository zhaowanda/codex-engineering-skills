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


build_index = load_module("build_index", ROOT / "skills/core/code-index-builder/scripts/build_index.py")
lookup_index = load_module("lookup_index", ROOT / "skills/core/code-index-lookup/scripts/lookup_index.py")
project_onboard = load_module("project_onboard", ROOT / "skills/core/project-onboard/scripts/project_onboard.py")
docs_governor = load_module("docs_governor", ROOT / "skills/core/docs-governor/scripts/docs_governor.py")
reverse_baseline = load_module("reverse_baseline", ROOT / "skills/core/project-baseline-reverser/scripts/reverse_baseline.py")
baseline_quality = load_module("baseline_quality_privacy", ROOT / "skills/core/baseline-quality-governor/scripts/baseline_quality.py")
project_understand = load_module(
    "project_understand", ROOT / "skills/core/project-understanding-runner/scripts/project_understand.py"
)
project_runner = load_module("project_runner", ROOT / "skills/core/project-runner/scripts/project_runner.py")


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
        result = project_onboard.onboard(
            "web-app",
            "/path/to/web-app",
            "frontend",
            overlay,
            "main",
            git_url="git@example.com:org/web-app.git",
            dependencies=["api-service"],
        )
        assert result["schema"] == "codex-project-onboard-v1"
        assert (overlay / "skills/web-app/SKILL.md").exists()
        references = overlay / "skills/web-app/references"
        expected = [
            "business-boundary.md",
            "feature-map.md",
            "api-map.md",
            "code-index.md",
            "change-playbook.md",
            "contract-patterns.json",
            "validation-recipes.md",
            "pitfalls.md",
            "Project edit gate",
            "review-cases.md",
        ]
        for name in expected:
            assert (references / name).exists()
        skill_text = (overlay / "skills/web-app/SKILL.md").read_text(encoding="utf-8")
        assert "references/business-boundary.md" in skill_text or "`business-boundary.md`" in skill_text
        assert result["reference_dir"].endswith("references")
        assert len(result["reference_files"]) == len(expected)
        assert "registry_entry" in result
        assert (overlay / "projects.yaml").exists()
        registry = (overlay / "projects.yaml").read_text(encoding="utf-8")
        assert "web-app" in registry
        assert "git@example.com:org/web-app.git" in registry
        assert "api-service" in registry
        assert "root:" not in registry
        assert "assets:" in registry
        assert "indexes/web-app.code_index.json" in registry
        assert "/path/to/web-app" not in skill_text
        assert "/path/to/web-app" not in (references / "code-index.md").read_text(encoding="utf-8")


def test_project_understanding_can_write_standard_project_skill() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = create_repo(root)
        out = root / "understanding"
        overlay = root / "overlay"
        result = project_understand.run(
            repo,
            "web-app",
            out,
            overlay_root=overlay,
            project_type="frontend",
            default_branch="main",
            write_project_skill=True,
            git_url="git@example.com:org/web-app.git",
            dependencies=["api-service"],
        )
        skill_dir = overlay / "skills/web-app"
        references = skill_dir / "references"
        assert result["project_skill"]["schema"] == "codex-project-onboard-v1"
        assert (skill_dir / "SKILL.md").exists()
        assert (references / "business-boundary.md").exists()
        assert (references / "feature-map.md").exists()
        assert (references / "api-map.md").exists()
        assert (references / "code-index.md").exists()
        assert (references / "change-playbook.md").exists()
        assert (references / "contract-patterns.json").exists()
        assert (references / "validation-recipes.md").exists()
        assert (references / "pitfalls.md").exists()
        assert (references / "Project edit gate").exists()
        assert (references / "review-cases.md").exists()
        assert "src/app.py" in (references / "code-index.md").read_text(encoding="utf-8")
        assert "/checkout" in (references / "api-map.md").read_text(encoding="utf-8")
        assert (overlay / "projects.yaml").exists()
        assert (overlay / "indexes/web-app.code_index.json").exists()
        assert (overlay / "baseline/web-app.baseline.json").exists()
        skill_bundle = "\n".join(
            path.read_text(encoding="utf-8") for path in [skill_dir / "SKILL.md", references / "business-boundary.md", references / "code-index.md"]
        )
        assert tmp not in skill_bundle
        assert "git@example.com:org/web-app.git" in skill_bundle


def test_project_runner_new_and_legacy_manage_project_assets() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = create_repo(root)
        overlay = root / "overlay"
        new_result = project_runner.run_new(
            "web-app",
            repo,
            "frontend",
            overlay,
            "main",
            git_url="git@example.com:org/web-app.git",
            dependencies=["api-service"],
        )
        assert new_result["schema"] == "codex-project-runner-summary-v1"
        assert new_result["decision"] in {"pass", "warn"}
        assert (overlay / "skills/web-app/SKILL.md").exists()
        assert (overlay / "projects.yaml").exists()
        assert (overlay / "indexes/web-app.code_index.json").exists()
        assert root.as_posix() not in (overlay / "skills/web-app/SKILL.md").read_text(encoding="utf-8")

        legacy_out = root / "understanding"
        legacy_result = project_runner.run_legacy(
            "web-app",
            repo,
            "frontend",
            overlay,
            "main",
            legacy_out,
            git_url="git@example.com:org/web-app.git",
            dependencies=["api-service"],
        )
        assert legacy_result["schema"] == "codex-project-runner-summary-v1"
        assert legacy_result["mode"] == "legacy"
        assert (overlay / "baseline/web-app.baseline.json").exists()
        assert "src/app.py" in (overlay / "skills/web-app/references/code-index.md").read_text(encoding="utf-8")
        assert root.as_posix() not in (overlay / "skills/web-app/references/code-index.md").read_text(encoding="utf-8")


def test_codex_eng_project_cli_uses_relative_project_assets() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = create_repo(root)
        overlay = root / "overlay"
        proc = subprocess.run(
            [
                "python3",
                "scripts/codex_eng.py",
                "project",
                "new",
                "--project",
                "web-app",
                "--repo",
                str(repo),
                "--type",
                "frontend",
                "--git-url",
                "git@example.com:org/web-app.git",
                "--depends-on",
                "api-service",
                "--overlay-root",
                str(overlay),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        registry = (overlay / "projects.yaml").read_text(encoding="utf-8")
        skill_text = (overlay / "skills/web-app/SKILL.md").read_text(encoding="utf-8")
        code_index_text = (overlay / "skills/web-app/references/code-index.md").read_text(encoding="utf-8")
        assert "repo:" in registry
        assert "git@example.com:org/web-app.git" in registry
        assert "dependencies:" in registry
        assert "api-service" in registry
        assert "assets:" in registry
        assert "root:" not in registry
        assert root.as_posix() not in skill_text
        assert root.as_posix() not in code_index_text


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


def test_baseline_quality_blocks_private_paths_and_secrets() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        baseline = Path(tmp) / "baseline.json"
        data = {
            "overview": "Leaked " + "/" + "Users/example/private and token=abc123",
            "module_hints": [{"module": "src"}],
            "api_surface_ref": "api_surface.json",
            "config_surface_ref": "config_surface.json",
            "dependency_surface_ref": "dependency_surface.json",
            "test_hints": ["tests/test_app.py"],
            "risk_hints": ["risk"],
            "limitations": ["owner review required"],
            "human_followups": ["confirm"],
        }
        baseline.write_text(json.dumps(data), encoding="utf-8")
        result = baseline_quality.review(baseline)
        assert result["decision"] == "block"
        sources = {item["source"] for item in result["blockers"]}
        assert {"local_path", "secret"}.issubset(sources)


def run_all() -> None:
    test_code_index_build_and_lookup()
    test_project_onboard_writes_skill_and_manifest()
    test_project_understanding_can_write_standard_project_skill()
    test_project_runner_new_and_legacy_manage_project_assets()
    test_codex_eng_project_cli_uses_relative_project_assets()
    test_docs_governor_init_and_validate()
    test_project_baseline_reverser_generates_summary()
    test_baseline_quality_blocks_private_paths_and_secrets()


if __name__ == "__main__":
    run_all()
    print("PASS project_understanding_governors tests")
