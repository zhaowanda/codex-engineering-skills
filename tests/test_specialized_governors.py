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
test_data = load_module("test_data", ROOT / "skills/core/test-data-governor/scripts/test_data.py")
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
    assert result["test_data_required"] is True
    assert result["test_data_plan_ref"] == "test_data_plan.json"
    assert all(case.get("test_data_refs") for case in result["test_cases"])
    assert all(case.get("cleanup_expectations") for case in result["test_cases"])
    assert any(case["type"] == "regression" for case in result["test_cases"])
    assert result["permission_scope"]
    assert result["integration_scope"]
    assert result["frontend_scope"]
    validation = test_design.validate_design(result)
    assert validation["decision"] == "pass"


def test_test_design_blocks_generic_steps() -> None:
    data = {
        "schema": "codex-test-design-v1",
        "acceptance_count": 1,
        "test_cases": [
            {
                "id": "TC-1",
                "acceptance_id": "AC-1",
                "type": "functional",
                "title": "generic",
                "steps": ["prepare data", "execute affected behavior", "verify expected result"],
                "expected_result": "passes",
                "evidence_required": ["test evidence"],
            }
        ],
        "regression_scope": [{"area": "changed behavior"}],
    }
    validation = test_design.validate_design(data)
    assert validation["decision"] == "block"
    assert any(item["source"] == "test_cases[0].steps" for item in validation["blockers"])


def test_test_data_governor_renders_plan_from_design() -> None:
    spec, technical, architecture = sample_docs()
    design = test_design.render(spec, technical, architecture)
    result = test_data.render(design)
    assert result["schema"] == "codex-test-data-plan-v1"
    assert result["decision"] == "pass"
    assert result["datasets"]
    assert result["case_data_matrix"]
    planned_ids = {item["id"] for item in result["datasets"]}
    required_ids = {ref for case in design["test_cases"] for ref in case["test_data_refs"]}
    assert required_ids.issubset(planned_ids)


def test_test_data_governor_blocks_sensitive_or_incomplete_data() -> None:
    plan = {
        "schema": "codex-test-data-plan-v1",
        "datasets": [
            {
                "id": "TD-TC-1",
                "case_ids": ["TC-1"],
                "data_classification": "production",
                "setup_method": "",
                "records": [{"name": "real customer fixture"}],
                "cleanup": [],
            }
        ],
        "case_data_matrix": [{"case_id": "TC-1", "dataset_ids": ["TD-TC-1"]}],
    }
    validation = test_data.validate_plan(plan)
    assert validation["decision"] == "block"
    messages = " ".join(item["message"] for item in validation["blockers"])
    assert "setup_method" in messages
    assert "cleanup" in messages
    assert "sensitive" in messages or "production" in messages


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
    test_test_design_blocks_generic_steps()
    test_test_data_governor_renders_plan_from_design()
    test_test_data_governor_blocks_sensitive_or_incomplete_data()
    test_configuration_detects_payment_email_database_and_blocks_missing_owners()
    test_performance_requires_evidence_for_api_database_export_ui()
    test_data_security_detects_sensitive_signals()


if __name__ == "__main__":
    run_all()
    print("PASS specialized_governors tests")
