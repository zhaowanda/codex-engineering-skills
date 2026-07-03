from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


issue_pr = load_module("issue_pr", ROOT / "skills/core/issue-pr-governor/scripts/issue_pr.py")
version_release = load_module("version_release", ROOT / "skills/core/version-release-governor/scripts/version_release.py")
dependency_license = load_module("dependency_license", ROOT / "skills/core/dependency-license-governor/scripts/dependency_license.py")
example_scenario = load_module("example_scenario", ROOT / "skills/core/example-scenario-runner/scripts/example_scenario.py")


def test_issue_pr_templates_pass() -> None:
    pr = issue_pr.review_pr(ROOT / ".github/pull_request_template.md")
    issues = issue_pr.review_issue_templates(ROOT)
    assert pr["decision"] == "pass"
    assert issues["decision"] == "pass"


def test_version_release_passes_current_project_version() -> None:
    result = version_release.review(ROOT, "0.1.0")
    assert result["schema"] == "codex-version-release-v1"
    assert result["decision"] == "pass"
    assert result["tag"] == "v0.1.0"


def test_version_release_blocks_missing_changelog_entry() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")
        (root / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
        result = version_release.review(root, "1.2.3")
        assert result["decision"] == "block"
        assert result["blockers"]


def test_dependency_license_passes_repo() -> None:
    result = dependency_license.review(ROOT)
    assert result["schema"] == "codex-dependency-license-v1"
    assert result["decision"] in {"pass", "warn"}
    assert result["license_file"] is True
    assert result["project_license"] == "MIT"


def test_dependency_license_blocks_missing_license() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text('[project]\nlicense = { text = "MIT" }\n', encoding="utf-8")
        result = dependency_license.review(root)
        assert result["decision"] == "block"


def test_example_scenario_runner_outputs_all_scenarios() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = example_scenario.run(ROOT, Path(tmp))
        assert result["schema"] == "codex-example-scenario-run-v1"
        assert result["decision"] == "pass"
        assert result["scenario_count"] == 8
        kinds = set()
        for case in result["cases"]:
            data = json.loads(Path(case["summary"]).read_text(encoding="utf-8"))
            kinds.add(data["kind"])
            assert data["spec"]["acceptance_criteria"]
            assert data["traceability"]["acceptance_covered"] is True
            assert data["risk"]["required_controls"]
            if case["name"] in {"cross-repo-api", "frontend-change", "data-migration", "release-readiness"}:
                assert data["replay"]["schema"] == "codex-delivery-replay-skeleton-v1"
                assert data["replay"]["artifact_count"] > 0
        assert {"bugfix", "small-feature", "config-change", "frontend-change", "cross-repo-api", "data-migration", "release-readiness", "code-review"}.issubset(kinds)


def run_all() -> None:
    test_issue_pr_templates_pass()
    test_version_release_passes_current_project_version()
    test_version_release_blocks_missing_changelog_entry()
    test_dependency_license_passes_repo()
    test_dependency_license_blocks_missing_license()
    test_example_scenario_runner_outputs_all_scenarios()


if __name__ == "__main__":
    run_all()
    print("PASS open_source_governors tests")
