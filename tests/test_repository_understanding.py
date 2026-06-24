from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/synthetic-repos/basic-web-service"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


repository_analyzer = load_module("repository_analyzer_new", ROOT / "skills/core/repository-analyzer/scripts/repository_analyzer.py")
api_surface = load_module("api_surface_new", ROOT / "skills/core/api-surface-extractor/scripts/api_surface.py")
config_surface = load_module("config_surface_new", ROOT / "skills/core/config-surface-extractor/scripts/config_surface.py")
dependency_surface = load_module("dependency_surface_new", ROOT / "skills/core/dependency-surface-analyzer/scripts/dependency_surface.py")
git_history = load_module("git_history_new", ROOT / "skills/core/git-history-miner/scripts/git_history.py")
project_understand = load_module("project_understand_new", ROOT / "skills/core/project-understanding-runner/scripts/project_understand.py")


def test_repository_analyzer_detects_structure() -> None:
    result = repository_analyzer.analyze(FIXTURE, "basic-web-service")
    assert result["schema"] == "codex-repository-analysis-v1"
    assert result["languages"]["python"] >= 2
    assert "fastapi" in result["framework_hints"]
    assert "pyproject.toml" in result["build_files"]
    assert "config/application.yml" in result["config_files"]
    assert ".github/workflows/test.yml" in result["ci_files"]
    assert any(path.endswith("tests/test_main.py") for path in result["test_hints"])


def test_api_config_dependency_and_git_extractors() -> None:
    api = api_surface.extract(FIXTURE, "basic-web-service")
    routes = {item["route"] for item in api["routes"]}
    assert "/health" in routes
    assert "/orders" in routes

    config = config_surface.extract(FIXTURE, "basic-web-service")
    rendered = json.dumps(config)
    assert "DATABASE_URL" not in rendered
    assert "PAYMENT_PROVIDER" not in rendered
    assert any(item["path"] == "config/application.yml" for item in config["config_items"])

    deps = dependency_surface.analyze(FIXTURE, "basic-web-service")
    assert "python" in deps["ecosystems"]
    assert "pytest" in deps["test_command_hints"]

    history = git_history.mine(FIXTURE, "basic-web-service")
    assert history["schema"] == "codex-git-history-mining-v1"
    assert history["decision"] in {"pass", "warn"}
    assert not history["blockers"]


def test_project_understanding_runner_writes_artifacts() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "understanding"
        result = project_understand.run(FIXTURE, "basic-web-service", out)
        assert result["schema"] == "codex-project-understanding-run-v1"
        assert result["decision"] in {"pass", "warn"}
        expected = {
            "repository_analysis.json",
            "api_surface.json",
            "config_surface.json",
            "dependency_surface.json",
            "git_history.json",
            "code_index.json",
            "baseline.json",
            "baseline_quality.json",
            "human_baseline.md",
        }
        assert expected == {path.name for path in out.iterdir()}
        assert (out / "human_baseline.md").read_text(encoding="utf-8").startswith("# basic-web-service Baseline")
        assert json.loads((out / "baseline_quality.json").read_text(encoding="utf-8"))["decision"] in {"pass", "warn"}


def test_project_understanding_runner_works_after_install_layout() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        installed = root / "skills/codex-engineering-skills"
        for name in [
            "repository-analyzer",
            "api-surface-extractor",
            "config-surface-extractor",
            "dependency-surface-analyzer",
            "git-history-miner",
            "code-index-builder",
            "project-baseline-reverser",
            "baseline-quality-governor",
            "project-understanding-runner",
        ]:
            shutil.copytree(ROOT / "skills/core" / name, installed / "core" / name)
        out = root / "out"
        proc = subprocess.run(
            [
                "python3",
                str(installed / "core/project-understanding-runner/scripts/project_understand.py"),
                "--repo",
                str(FIXTURE),
                "--project",
                "basic-web-service",
                "--out",
                str(out),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert (out / "human_baseline.md").exists()


def test_project_understanding_runner_works_with_overlay_category_layout() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        installed = root / "skills"
        open_core = installed / "open-core"
        company = installed / "company"
        for name in [
            "repository-analyzer",
            "api-surface-extractor",
            "config-surface-extractor",
            "dependency-surface-analyzer",
            "git-history-miner",
            "project-baseline-reverser",
            "baseline-quality-governor",
            "project-understanding-runner",
        ]:
            shutil.copytree(ROOT / "skills/core" / name, open_core / name)
        shutil.copytree(ROOT / "skills/core/code-index-builder", company / "code-index-builder")
        out = root / "out"
        proc = subprocess.run(
            [
                "python3",
                str(open_core / "project-understanding-runner/scripts/project_understand.py"),
                "--repo",
                str(FIXTURE),
                "--project",
                "basic-web-service",
                "--out",
                str(out),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr
        assert (out / "human_baseline.md").exists()


def run_all() -> None:
    test_repository_analyzer_detects_structure()
    test_api_config_dependency_and_git_extractors()
    test_project_understanding_runner_writes_artifacts()
    test_project_understanding_runner_works_after_install_layout()
    test_project_understanding_runner_works_with_overlay_category_layout()


if __name__ == "__main__":
    run_all()
    print("PASS repository_understanding tests")
