from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


test_design = load_module("test_design", ROOT / "skills/core/test-design-governor/scripts/test_design.py")
configuration = load_module("configuration", ROOT / "skills/core/configuration-governor/scripts/configuration.py")
performance = load_module("performance", ROOT / "skills/core/performance-governor/scripts/performance.py")
data_security = load_module("data_security", ROOT / "skills/core/data-security-governor/scripts/data_security.py")


def sample_docs():
    spec = {
        "doc_id": "REQ-1",
        "title": "Admin export",
        "requirement_summary": "Admin exports tenant payment report by email.",
        "requirements": [{"id": "REQ-1", "summary": "Admin exports tenant payment report"}],
        "acceptance_criteria": [{"id": "AC-1", "criteria": "Only admin can export filtered payment report", "evidence_required": ["test evidence"]}],
    }
    technical = {
        "doc_id": "REQ-1",
        "title": "Admin export",
        "api_contracts": [{"contract": "export API", "compatibility": "additive", "old_consumer_impact": "none"}],
        "ui_ue_design": [{"page_or_route": "/reports"}],
        "permission_model": [{"role": "admin", "rule": "tenant scope"}],
        "test_strategy": [{"case": "admin export"}],
    }
    architecture = {
        "doc_id": "REQ-1",
        "title": "Admin export",
        "repo_responsibilities": [
            {"repo": "web-app", "role": "modify"},
            {"repo": "api-service", "role": "modify"},
        ],
        "data_flow": [{"source": "database", "target": "export"}],
    }
    return spec, technical, architecture


def test_test_design_maps_acceptance_and_special_scopes() -> None:
    spec, technical, architecture = sample_docs()
    result = test_design.render(spec, technical, architecture)
    assert result["schema"] == "codex-test-design-v1"
    assert result["acceptance_count"] == 1
    assert result["permission_scope"]
    assert result["integration_scope"]
    assert result["frontend_scope"]
    validation = test_design.validate_design(result)
    assert validation["decision"] == "pass"


def test_configuration_detects_payment_email_database_and_blocks_missing_owners() -> None:
    spec, technical, architecture = sample_docs()
    result = configuration.analyze(spec, technical, architecture)
    assert result["schema"] == "codex-configuration-readiness-v1"
    kinds = {item["type"] for item in result["configuration_items"]}
    assert {"payment", "email", "database"}.issubset(kinds)
    assert result["decision"] == "blocked"
    assert result["blockers"]


def test_performance_requires_evidence_for_api_database_export_ui() -> None:
    spec, technical, architecture = sample_docs()
    result = performance.design_review(spec, technical, architecture)
    assert result["schema"] == "codex-performance-review-v1"
    assert result["decision"] == "needs_evidence"
    areas = {item["area"] for item in result["evidence_plan"]}
    assert "api" in areas
    assert "database" in areas
    assert "throughput" in areas
    assert "frontend" in areas


def test_data_security_detects_sensitive_signals() -> None:
    spec, technical, architecture = sample_docs()
    result = data_security.design_review(spec, technical, architecture)
    assert result["schema"] == "codex-data-security-review-v1"
    assert result["decision"] == "needs_review"
    assert "payment" in result["sensitive_signals"]
    assert result["controls_required"]


def run_all() -> None:
    test_test_design_maps_acceptance_and_special_scopes()
    test_configuration_detects_payment_email_database_and_blocks_missing_owners()
    test_performance_requires_evidence_for_api_database_export_ui()
    test_data_security_detects_sensitive_signals()


if __name__ == "__main__":
    run_all()
    print("PASS specialized_governors tests")
