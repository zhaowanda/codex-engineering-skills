from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "skills/core/design-architecture-reviewer/scripts/design_arch_review.py"
spec = importlib.util.spec_from_file_location("design_arch_review", SCRIPT)
design_arch_review = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(design_arch_review)


def complete_design() -> tuple[dict, dict]:
    technical = {
        "design_scope": {"in_scope": ["checkout discount display"], "out_of_scope": ["payment capture"], "assumptions": ["existing API"], "non_goals": ["schema change"]},
        "requirement_trace": [{"requirement_id": "REQ-1", "summary": "show discount breakdown on checkout page"}],
        "business_rule_mapping": [{"requirement_id": "REQ-1", "technical_enforcement": "frontend renders server discount fields", "source_of_truth": "pricing API response"}],
        "process_flow": [{"flow_name": "checkout review", "actors": ["buyer"], "steps": [{"step": 1, "actor": "buyer", "action": "open checkout", "input": "cart", "output": "discount breakdown", "exception": "API error shows fallback"}], "success_end_state": "discount is visible before submit", "failure_end_states": ["pricing unavailable"]}],
        "module_decomposition": [{"module": "checkout-summary", "responsibility": "render discount rows", "input": "pricing response", "output": "summary UI", "dependencies": ["pricing API"], "cohesion_reason": "presentation only", "coupling_control": "no pricing calculation in UI"}],
        "logical_data_flow": [{"source": "pricing API", "transform": "format discount rows", "destination": "checkout summary", "owner": "pricing-service", "data_security": "no sensitive personal data"}],
        "target_behavior": [{"requirement_id": "REQ-1", "behavior": "buyer sees discount breakdown"}],
        "api_contracts": [{"contract": "discounts[] field unchanged", "compatibility": "additive rendering only", "old_consumer_impact": "none"}],
        "compatibility_strategy": [{"old_consumer": "checkout page", "old_data": "orders without discounts", "rollback": "hide rows", "behavior": "empty discounts render nothing"}],
        "data_design": [{"read_rule": "read existing discounts array", "write_rule": "no write", "migration": "none"}],
        "permission_model": [{"role": "buyer", "rule": "own checkout only", "negative_case": "cannot view other carts"}],
        "exception_and_edge_cases": [{"case": "discounts missing", "handling": "show subtotal only"}],
        "non_functional_requirements": [{"type": "performance", "impact": "no extra request"}],
        "solution_options": [
            {"option_id": "T1", "name": "render existing API field", "description": "UI-only render", "pros": ["small"], "cons": ["depends on API"], "risk_level": "low", "validation": "browser evidence", "performance_impact": "none", "rollback_strategy": "revert UI"},
            {"option_id": "T2", "name": "calculate in frontend", "description": "derive discounts in UI", "pros": ["independent"], "cons": ["business logic duplicate"], "risk_level": "high", "validation": "unit tests", "performance_impact": "minor CPU", "rollback_strategy": "revert UI"},
        ],
        "selected_solution": {"selected_option_id": "T1", "selection_reason": "keeps pricing source of truth", "decision_criteria": ["correctness", "low coupling"], "tradeoffs": ["UI depends on existing field"], "rejected_alternative_reasoning": [{"option_id": "T2", "reason": "duplicates pricing logic"}]},
        "design_traceability_matrix": [{"requirement_id": "REQ-1", "process_flow_refs": ["checkout review"], "module_refs": ["checkout-summary"], "data_flow_refs": ["pricing API->checkout summary"], "api_contract_refs": ["discounts[]"], "ui_ue_refs": ["checkout summary"], "test_refs": ["UI-1"], "acceptance_refs": ["AC-1"], "selected_option_id": "T1", "decision_reason": "lowest risk"}],
        "acceptance_mapping": [{"acceptance_id": "AC-1", "design_refs": ["checkout summary"], "evidence_required": ["browser screenshot"]}],
        "ui_ue_design": [{"page_or_route": "/checkout", "user_goal": "confirm price", "entry_point": "cart checkout", "layout": "summary panel", "interaction_flow": ["open page"], "states": ["loading", "success", "error"], "field_rules": ["show each discount label and amount"], "permission_visibility": "buyer own cart", "acceptance_evidence": "browser screenshot"}],
        "test_strategy": [{"case": "discount breakdown visible", "evidence": "browser"}],
    }
    architecture = {
        "architecture_scope": {"in_scope": ["web checkout"], "out_of_scope": ["pricing service"], "assumptions": ["contract exists"], "decision_drivers": ["low coupling"]},
        "architecture_options": [
            {"option_id": "A1", "name": "web only", "description": "render existing contract", "owner_repos": ["web-app"], "confirm_only_repos": ["pricing-service"], "pros": ["safe"], "cons": ["UI local"], "risk_level": "low", "validation": "browser", "performance_impact": "none", "rollback_strategy": "revert web"},
            {"option_id": "A2", "name": "pricing API change", "description": "new endpoint", "owner_repos": ["pricing-service", "web-app"], "confirm_only_repos": ["reporting-service"], "pros": ["explicit"], "cons": ["contract risk"], "risk_level": "medium", "validation": "API+UI", "performance_impact": "extra request", "rollback_strategy": "revert both"},
        ],
        "selected_architecture": {"selected_option_id": "A1", "selection_reason": "no API change", "decision_criteria": ["compatibility", "low coupling"], "tradeoffs": ["UI renders existing data"], "rejected_alternative_reasoning": [{"option_id": "A2", "reason": "adds contract risk"}]},
        "architecture_traceability_matrix": [{"requirement_id": "REQ-1", "component_boundary_refs": ["web-app owns rendering"], "module_topology_refs": ["web-app/checkout-summary"], "data_flow_refs": ["pricing-service->web-app"], "integration_sequence_refs": ["checkout load"], "contract_refs": ["discounts[]"], "selected_architecture_option_id": "A1", "decision_reason": "lowest integration risk"}],
        "component_boundaries": [{"component": "web-app", "role": "render", "exclusion": "no pricing calculation"}],
        "module_topology": [{"repo": "web-app", "module": "checkout-summary", "responsibility": "display", "depends_on": ["pricing-service"], "boundary_rule": "read-only API consumer", "change_type": "modify"}],
        "repo_responsibilities": [{"repo": "web-app", "role": "modify", "responsibility": "render discount rows"}, {"repo": "pricing-service", "role": "confirm_only", "responsibility": "contract unchanged"}],
        "cross_repo_contracts": [{"producer": "pricing-service", "consumer": "web-app", "contract": "discounts[]", "compatibility": "unchanged", "failure_mode": "empty discounts render none"}],
        "data_flow": [{"source": "pricing-service", "target": "web-app", "rule": "display only"}],
        "data_ownership": [{"business_object": "discount", "owner_repo": "pricing-service", "write_authority": "pricing-service", "consistency_rule": "web read only"}],
        "integration_sequence": [{"step": 1, "actor": "web-app", "action": "load pricing", "failure_handling": "show existing error"}],
        "security_and_permission": [{"control": "cart ownership enforced by API", "impact": "no new permission"}],
        "observability": [{"signal": "frontend error log", "owner": "web team"}],
        "monitoring_alerts": [{"signal": "checkout JS error", "owner": "web team", "trigger": "error increase", "action": "rollback"}],
        "deployment_topology": [{"repo": "web-app", "artifact": "frontend bundle", "environment": "standard"}],
        "deployment_impact": [{"order": "web only", "config": "none"}],
        "migration_strategy": [{"migration_type": "none", "forward_action": "deploy web", "backward_compatibility": "API unchanged", "rollback_action": "revert web"}],
        "gray_release_strategy": [{"strategy": "normal web rollout", "fallback": "rollback"}],
        "rollback_strategy": [{"repo": "web-app", "steps": ["revert commit", "redeploy"], "data_risk": "none"}],
        "decision_records": [{"decision": "web-only rendering", "alternatives": ["API change"], "reason": "lower risk"}],
    }
    return technical, architecture


def test_thin_design_blocks() -> None:
    result = design_arch_review.review({"requirement_trace": [{"requirement_id": "REQ-1"}]}, {})
    assert result["schema"] == "codex-design-architecture-review-v1"
    assert result["decision"] == "block"
    assert result["score"] < 60
    assert not result["readiness_gate"]["implementation_allowed"]


def test_complete_design_passes() -> None:
    technical, architecture = complete_design()
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "pass"
    assert result["score"] >= 85
    assert result["readiness_gate"]["implementation_allowed"]
    valid, issues = design_arch_review.validate(result)
    assert valid, issues


def test_missing_option_comparison_needs_revision() -> None:
    technical, architecture = complete_design()
    technical["solution_options"] = technical["solution_options"][:1]
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "needs_revision"
    assert not result["readiness_gate"]["implementation_allowed"]
    assert result["severity_counts"]["high"] >= 1


def test_missing_rejected_alternative_reasoning_needs_revision() -> None:
    technical, architecture = complete_design()
    technical["selected_solution"].pop("rejected_alternative_reasoning")
    architecture["selected_architecture"].pop("rejected_alternative_reasoning")
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "needs_revision"
    assert not result["readiness_gate"]["implementation_allowed"]
    messages = json_dumps(result)
    assert "rejected alternative reasoning" in messages


def json_dumps(value: dict) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


def run_all() -> None:
    test_thin_design_blocks()
    test_complete_design_passes()
    test_missing_option_comparison_needs_revision()
    test_missing_rejected_alternative_reasoning_needs_revision()


if __name__ == "__main__":
    run_all()
    print("PASS design_architecture_reviewer tests")
