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


contribution = load_module("contribution", ROOT / "skills/core/contribution-governor/scripts/contribution.py")
security_policy = load_module("security_policy", ROOT / "skills/core/security-policy-governor/scripts/security_policy.py")
docs_site = load_module("docs_site", ROOT / "skills/core/docs-site-governor/scripts/docs_site.py")
compatibility = load_module("compatibility", ROOT / "skills/core/compatibility-governor/scripts/compatibility.py")
mcp_integration = load_module("mcp_integration", ROOT / "skills/core/mcp-integration-governor/scripts/mcp_integration.py")
benchmark = load_module("benchmark", ROOT / "skills/core/benchmark-governor/scripts/benchmark.py")


def test_contribution_governor_passes_repo() -> None:
    result = contribution.review(ROOT)
    assert result["schema"] == "codex-contribution-governance-v1"
    assert result["decision"] == "pass"


def test_contribution_governor_blocks_missing_file() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = contribution.review(Path(tmp))
        assert result["decision"] == "block"


def test_security_policy_governor_passes_repo() -> None:
    result = security_policy.review(ROOT)
    assert result["schema"] == "codex-security-policy-v1"
    assert result["decision"] == "pass"


def test_docs_site_governor_passes_repo() -> None:
    result = docs_site.validate(ROOT)
    assert result["schema"] == "codex-docs-site-v1"
    assert result["decision"] == "pass"


def test_compatibility_governor_passes_against_head() -> None:
    result = compatibility.review(ROOT, "HEAD")
    assert result["schema"] == "codex-compatibility-review-v1"
    assert result["decision"] == "pass"
    assert result["current_counts"]["skills"] >= 50


def test_mcp_integration_governor_warns_or_passes_repo() -> None:
    result = mcp_integration.review(ROOT)
    assert result["schema"] == "codex-mcp-integration-v1"
    assert result["decision"] in {"pass", "warn"}
    assert not result["blockers"]


def test_benchmark_governor_reports_metrics() -> None:
    result = benchmark.report(ROOT)
    assert result["schema"] == "codex-benchmark-report-v1"
    assert result["decision"] == "pass"
    assert result["metrics"]["skill_count"] >= 50
    assert result["metrics"]["privacy_decision"] == "pass"
    assert result["metrics"]["skill_health_decision"] == "pass"
    assert result["metrics"]["skill_content_quality_average"] > 0
    assert result["metrics"]["replay_validation_decision"] == "pass"
    assert result["metrics"]["replay_case_count"] >= 4


def run_all() -> None:
    test_contribution_governor_passes_repo()
    test_contribution_governor_blocks_missing_file()
    test_security_policy_governor_passes_repo()
    test_docs_site_governor_passes_repo()
    test_compatibility_governor_passes_against_head()
    test_mcp_integration_governor_warns_or_passes_repo()
    test_benchmark_governor_reports_metrics()


if __name__ == "__main__":
    run_all()
    print("PASS open_source_maturity_governors tests")
