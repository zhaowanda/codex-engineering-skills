#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def empty_technical(doc_id: str, title: str) -> dict[str, Any]:
    return {
        "schema": "codex-technical-design-v1",
        "doc_id": doc_id,
        "title": title,
        "design_scope": {"in_scope": [], "out_of_scope": [], "assumptions": [], "non_goals": []},
        "current_state_analysis": {"existing_behavior": "", "code_entrypoints": [], "known_constraints": [], "reuse_points": []},
        "requirement_trace": [],
        "business_rule_mapping": [],
        "process_flow": [
            {
                "flow_name": "",
                "actors": [],
                "steps": [{"step": 1, "actor": "", "action": "", "input": "", "output": "", "exception": ""}],
                "success_end_state": "",
                "failure_end_states": [],
            }
        ],
        "module_decomposition": [
            {"module": "", "responsibility": "", "input": "", "output": "", "dependencies": [], "cohesion_reason": "", "coupling_control": ""}
        ],
        "logical_data_flow": [
            {"source": "", "transform": "", "destination": "", "owner": "", "data_security": ""}
        ],
        "target_behavior": [],
        "api_contracts": [],
        "interface_examples": [],
        "compatibility_strategy": [],
        "compatibility_matrix": [],
        "data_design": [{"read_rule": "", "write_rule": "", "migration": ""}],
        "permission_model": [],
        "exception_and_edge_cases": [],
        "non_functional_requirements": [{"type": "performance", "impact": ""}, {"type": "security", "impact": ""}],
        "solution_options": [
            {"option_id": "T1", "name": "", "description": "", "when_to_choose": [], "implementation_outline": [], "pros": [], "cons": [], "risk_level": "", "risk_controls": [], "validation": "", "test_evidence": [], "performance_impact": "", "rollout_impact": "", "rollback_strategy": ""},
            {"option_id": "T2", "name": "", "description": "", "when_to_choose": [], "implementation_outline": [], "pros": [], "cons": [], "risk_level": "", "risk_controls": [], "validation": "", "test_evidence": [], "performance_impact": "", "rollout_impact": "", "rollback_strategy": ""},
        ],
        "option_comparison_matrix": [],
        "option_score_summary": {},
        "selected_solution": {"selected_option_id": "", "selection_reason": "", "decision_criteria": [], "tradeoffs": [], "rejected_alternative_reasoning": []},
        "design_traceability_matrix": [],
        "acceptance_mapping": [],
        "ui_ue_design": [],
        "test_strategy": [],
        "test_design_ref": "test_design.json",
        "open_questions": [],
    }


def empty_architecture(doc_id: str, title: str) -> dict[str, Any]:
    return {
        "schema": "codex-architecture-design-v1",
        "doc_id": doc_id,
        "title": title,
        "architecture_scope": {"in_scope": [], "out_of_scope": [], "assumptions": [], "decision_drivers": []},
        "current_architecture": {"system_context": "", "repo_entrypoints": [], "upstream_downstream": [], "constraints": []},
        "architecture_options": [
            {"option_id": "A1", "name": "", "description": "", "when_to_choose": [], "owner_repos": [], "confirm_only_repos": [], "integration_impact": "", "deployment_impact": "", "rollback_complexity": "", "pros": [], "cons": [], "risk_level": "", "risk_controls": [], "validation": "", "performance_impact": "", "rollback_strategy": ""},
            {"option_id": "A2", "name": "", "description": "", "when_to_choose": [], "owner_repos": [], "confirm_only_repos": [], "integration_impact": "", "deployment_impact": "", "rollback_complexity": "", "pros": [], "cons": [], "risk_level": "", "risk_controls": [], "validation": "", "performance_impact": "", "rollback_strategy": ""},
        ],
        "architecture_fit_matrix": [],
        "architecture_score_summary": {},
        "selected_architecture": {"selected_option_id": "", "selection_reason": "", "decision_criteria": [], "tradeoffs": [], "rejected_alternative_reasoning": []},
        "architecture_traceability_matrix": [],
        "component_boundaries": [],
        "module_topology": [],
        "repo_responsibilities": [],
        "cross_repo_contracts": [],
        "cross_repo_dependency_graph": [],
        "data_flow": [],
        "data_ownership": [],
        "integration_sequence": [],
        "failure_isolation": [],
        "security_and_permission": [],
        "observability": [],
        "monitoring_alerts": [],
        "deployment_topology": [],
        "deployment_impact": [],
        "deployment_impact_matrix": [],
        "migration_strategy": [],
        "gray_release_strategy": [],
        "rollback_strategy": [],
        "decision_records": [],
        "architecture_risks": [],
    }


def example_technical(doc_id: str, title: str) -> dict[str, Any]:
    data = empty_technical(doc_id, title)
    data.update({
        "design_scope": {"in_scope": ["checkout discount display"], "out_of_scope": ["payment capture"], "assumptions": ["pricing API already returns discounts"], "non_goals": ["pricing calculation change"]},
        "current_state_analysis": {"existing_behavior": "checkout summary already renders subtotal and total from the pricing API response", "code_entrypoints": ["src/checkout/CheckoutSummary.tsx", "src/checkout/usePricing.ts"], "known_constraints": ["pricing calculation must remain server-owned", "no additional checkout request is allowed"], "reuse_points": ["existing summary row renderer", "existing pricing response type"]},
        "requirement_trace": [{"requirement_id": "REQ-1", "summary": "show discount breakdown on checkout page"}],
        "business_rule_mapping": [{"requirement_id": "REQ-1", "technical_enforcement": "web page renders server discount fields", "source_of_truth": "pricing API response"}],
        "process_flow": [{"flow_name": "checkout review", "actors": ["buyer"], "steps": [{"step": 1, "actor": "buyer", "action": "open checkout", "input": "cart", "output": "discount breakdown", "exception": "pricing error shows existing fallback"}], "success_end_state": "discount is visible before submit", "failure_end_states": ["pricing unavailable"]}],
        "module_decomposition": [{"module": "src/checkout/CheckoutSummary.tsx", "responsibility": "render discount rows", "input": "pricing response", "output": "summary UI", "dependencies": ["pricing API"], "cohesion_reason": "presentation-only module", "coupling_control": "no pricing calculation in UI"}],
        "logical_data_flow": [{"source": "pricing API", "transform": "format discount rows", "destination": "checkout summary", "owner": "pricing-service", "data_security": "no sensitive personal data"}],
        "target_behavior": [{"requirement_id": "REQ-1", "behavior": "buyer sees discount breakdown before order submission"}],
        "api_contracts": [{"contract": "discounts[] field unchanged", "compatibility": "additive rendering only", "old_consumer_impact": "none"}],
        "interface_examples": [{"name": "pricing response", "request": "GET /api/pricing?cartId={cartId}", "response": "{\"discounts\":[{\"label\":\"Coupon\",\"amount\":-500}]}", "error_response": "{\"error\":\"pricing unavailable\"}"}],
        "compatibility_strategy": [{"old_consumer": "checkout page", "old_data": "orders without discounts", "rollback": "hide rows", "behavior": "empty discounts render nothing"}],
        "compatibility_matrix": [{"consumer": "checkout page", "old_behavior": "subtotal and total only", "new_behavior": "discount rows displayed when present", "compatibility": "additive", "rollback_behavior": "discount rows hidden"}],
        "data_design": [{"read_rule": "read existing discounts array", "write_rule": "no write", "migration": "none"}],
        "permission_model": [{"role": "buyer", "rule": "own checkout only", "negative_case": "cannot view other carts"}],
        "exception_and_edge_cases": [{"case": "discounts missing", "handling": "show subtotal only"}],
        "non_functional_requirements": [{"type": "performance", "impact": "no extra request"}, {"type": "security", "impact": "no new sensitive data"}],
        "solution_options": [
            {"option_id": "T1", "name": "render existing API field", "description": "UI-only render", "when_to_choose": ["pricing API already returns discounts", "acceptance only changes checkout display"], "implementation_outline": ["read CheckoutSummary and usePricing", "render discount rows from existing response", "preserve existing fallback when discounts are absent"], "pros": ["small change", "keeps pricing source of truth"], "cons": ["depends on existing field", "less reusable if other pages need discounts"], "risk_level": "low", "risk_controls": ["browser regression", "no pricing calculation in UI"], "validation": "browser evidence", "test_evidence": ["browser screenshot", "checkout regression output"], "performance_impact": "none", "rollout_impact": "web bundle only", "rollback_strategy": "revert UI"},
            {"option_id": "T2", "name": "calculate in web", "description": "derive discounts in UI", "when_to_choose": ["API cannot expose discount breakdown", "temporary display is accepted by pricing owner"], "implementation_outline": ["read pricing inputs", "derive discount rows in web", "add unit tests for pricing edge cases"], "pros": ["independent", "fast local change"], "cons": ["duplicates pricing logic", "higher correctness risk"], "risk_level": "high", "risk_controls": ["pricing owner review", "unit tests for edge cases"], "validation": "unit tests", "test_evidence": ["unit test output", "browser screenshot"], "performance_impact": "minor CPU", "rollout_impact": "web bundle only but pricing behavior risk increases", "rollback_strategy": "revert UI"},
        ],
        "option_comparison_matrix": [
            {"criterion": "correctness", "weight": 5, "scores": {"T1": 5, "T2": 2}, "winner": "T1", "reason": "pricing remains source of truth"},
            {"criterion": "blast_radius", "weight": 5, "scores": {"T1": 5, "T2": 4}, "winner": "T1", "reason": "render-only change"},
            {"criterion": "rollback", "weight": 4, "scores": {"T1": 5, "T2": 5}, "winner": "tie", "reason": "both rollback by reverting web"},
            {"criterion": "test_surface", "weight": 4, "scores": {"T1": 4, "T2": 3}, "winner": "T1", "reason": "less pricing logic to validate"},
        ],
        "option_score_summary": {"T1": 96, "T2": 67, "scoring_rule": "weighted qualitative score"},
        "selected_solution": {"selected_option_id": "T1", "selection_reason": "keeps pricing source of truth", "decision_criteria": ["correctness", "low coupling"], "tradeoffs": ["UI depends on existing field"], "rejected_alternative_reasoning": [{"option_id": "T2", "reason": "duplicates pricing logic in the UI"}]},
        "design_traceability_matrix": [{"requirement_id": "REQ-1", "process_flow_refs": ["checkout review"], "module_refs": ["src/checkout/CheckoutSummary.tsx"], "data_flow_refs": ["pricing API->checkout summary"], "api_contract_refs": ["discounts[]"], "ui_ue_refs": ["checkout summary"], "test_refs": ["UI-1"], "acceptance_refs": ["AC-1"], "selected_option_id": "T1", "decision_reason": "lowest risk"}],
        "acceptance_mapping": [{"acceptance_id": "AC-1", "design_refs": ["checkout summary"], "evidence_required": ["browser screenshot"]}],
        "ui_ue_design": [{"page_or_route": "/checkout", "user_goal": "confirm price", "entry_point": "cart checkout", "layout": "summary panel", "interaction_flow": ["open page"], "states": ["loading", "success", "error"], "field_rules": ["show each discount label and amount"], "permission_visibility": "buyer own cart", "acceptance_evidence": "browser screenshot"}],
        "test_strategy": [{"summary": "browser, regression, and acceptance evidence required", "evidence": ["browser screenshot", "regression evidence"], "test_design_ref": "test_design.json"}],
        "test_design_ref": "test_design.json",
    })
    return data


def example_architecture(doc_id: str, title: str) -> dict[str, Any]:
    data = empty_architecture(doc_id, title)
    data.update({
        "architecture_scope": {"in_scope": ["web checkout"], "out_of_scope": ["pricing service logic"], "assumptions": ["contract exists"], "decision_drivers": ["low coupling"]},
        "current_architecture": {"system_context": "web-app consumes pricing-service during checkout and renders the returned summary", "repo_entrypoints": ["web-app/src/checkout/CheckoutSummary.tsx", "pricing-service existing pricing endpoint"], "upstream_downstream": ["pricing-service -> web-app"], "constraints": ["pricing-service remains source of truth"]},
        "architecture_options": [
            {"option_id": "A1", "name": "web only", "description": "render existing contract", "when_to_choose": ["discounts[] contract already exists", "web-app only changes presentation"], "owner_repos": ["web-app"], "confirm_only_repos": ["pricing-service"], "integration_impact": "no new provider-consumer contract", "deployment_impact": "deploy web bundle only", "rollback_complexity": "low", "pros": ["safe", "low coordination"], "cons": ["UI local", "less reusable"], "risk_level": "low", "risk_controls": ["contract confirmation", "browser evidence"], "validation": "browser", "performance_impact": "none", "rollback_strategy": "revert web"},
            {"option_id": "A2", "name": "pricing API change", "description": "new endpoint", "when_to_choose": ["contract lacks required discount data", "multiple consumers need the same shape"], "owner_repos": ["pricing-service", "web-app"], "confirm_only_repos": ["reporting-service"], "integration_impact": "provider-consumer contract and integration tests", "deployment_impact": "pricing-service before web-app or compatible rollout", "rollback_complexity": "medium", "pros": ["explicit", "shared"], "cons": ["contract risk", "ordered release"], "risk_level": "medium", "risk_controls": ["contract freeze", "integration evidence"], "validation": "API+UI", "performance_impact": "extra request or payload growth", "rollback_strategy": "revert both"},
        ],
        "architecture_fit_matrix": [
            {"criterion": "ownership_clarity", "weight": 5, "scores": {"A1": 5, "A2": 3}, "winner": "A1", "reason": "web owns rendering"},
            {"criterion": "release_coordination", "weight": 5, "scores": {"A1": 5, "A2": 2}, "winner": "A1", "reason": "web-only deploy"},
            {"criterion": "contract_risk", "weight": 5, "scores": {"A1": 5, "A2": 2}, "winner": "A1", "reason": "contract unchanged"},
            {"criterion": "rollback", "weight": 4, "scores": {"A1": 5, "A2": 3}, "winner": "A1", "reason": "single repo rollback"},
        ],
        "architecture_score_summary": {"A1": 95, "A2": 70, "scoring_rule": "weighted qualitative score"},
        "selected_architecture": {"selected_option_id": "A1", "selection_reason": "no API change", "decision_criteria": ["compatibility", "low coupling"], "tradeoffs": ["UI renders existing data"], "rejected_alternative_reasoning": [{"option_id": "A2", "reason": "adds cross-repo contract and release-order risk"}]},
        "architecture_traceability_matrix": [{"requirement_id": "REQ-1", "component_boundary_refs": ["web-app owns rendering"], "module_topology_refs": ["web-app/checkout-summary"], "data_flow_refs": ["pricing-service->web-app"], "integration_sequence_refs": ["checkout load"], "contract_refs": ["discounts[]"], "selected_architecture_option_id": "A1", "decision_reason": "lowest integration risk"}],
        "component_boundaries": [{"component": "web-app", "role": "render", "exclusion": "no pricing calculation"}],
        "module_topology": [{"repo": "web-app", "module": "checkout-summary", "responsibility": "display", "depends_on": ["pricing-service"], "boundary_rule": "read-only API consumer", "change_type": "modify"}],
        "repo_responsibilities": [{"repo": "web-app", "role": "modify", "responsibility": "render discount rows"}, {"repo": "pricing-service", "role": "confirm_only", "responsibility": "contract unchanged"}],
        "cross_repo_contracts": [{"producer": "pricing-service", "consumer": "web-app", "contract": "discounts[]", "compatibility": "unchanged", "failure_mode": "empty discounts render none"}],
        "cross_repo_dependency_graph": [{"from": "pricing-service", "to": "web-app", "contract": "pricing response discounts[]", "change": "confirm only"}],
        "data_flow": [{"source": "pricing-service", "target": "web-app", "rule": "display only"}],
        "data_ownership": [{"business_object": "discount", "owner_repo": "pricing-service", "write_authority": "pricing-service", "consistency_rule": "web read only"}],
        "integration_sequence": [{"step": 1, "actor": "web-app", "action": "load pricing", "failure_handling": "show existing error"}],
        "failure_isolation": [{"failure": "pricing response omits discounts", "isolation": "checkout summary renders subtotal only", "user_impact": "no checkout block"}],
        "security_and_permission": [{"control": "cart ownership enforced by API", "impact": "no new permission"}],
        "observability": [{"signal": "frontend error log", "owner": "web team"}],
        "monitoring_alerts": [{"signal": "checkout JS error", "owner": "web team", "trigger": "error increase", "action": "rollback"}],
        "deployment_topology": [{"repo": "web-app", "artifact": "frontend bundle", "environment": "standard"}],
        "deployment_impact": [{"order": "web only", "config": "none"}],
        "deployment_impact_matrix": [{"repo": "web-app", "artifact": "frontend bundle", "order": 1, "config_change": "none", "restart_required": "standard web deploy"}],
        "migration_strategy": [{"migration_type": "none", "forward_action": "deploy web", "backward_compatibility": "API unchanged", "rollback_action": "revert web"}],
        "gray_release_strategy": [{"strategy": "normal web rollout", "fallback": "rollback"}],
        "rollback_strategy": [{"repo": "web-app", "steps": ["revert commit", "redeploy"], "data_risk": "none"}],
        "decision_records": [{"decision": "web-only rendering", "alternatives": ["API change"], "reason": "lower risk"}],
    })
    return data


def render(doc_id: str, title: str, out_dir: Path, example: bool = False) -> dict[str, Any]:
    technical = example_technical(doc_id, title) if example else empty_technical(doc_id, title)
    architecture = example_architecture(doc_id, title) if example else empty_architecture(doc_id, title)
    write_json(out_dir / "technical_design.json", technical)
    write_json(out_dir / "architecture_design.json", architecture)
    manifest = {
        "schema": "codex-design-template-manifest-v1",
        "doc_id": doc_id,
        "title": title,
        "example": example,
        "files": {
            "technical_design": str((out_dir / "technical_design.json").resolve()),
            "architecture_design": str((out_dir / "architecture_design.json").resolve()),
        },
        "next_action": "fill concrete facts and run design-architecture-reviewer" if not example else "run design-architecture-reviewer regression",
        "generated_at": now(),
    }
    write_json(out_dir / "design_template_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Render technical and architecture design templates")
    parser.add_argument("--doc-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--example", action="store_true")
    args = parser.parse_args()
    manifest = render(args.doc_id, args.title, Path(args.out_dir), args.example)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
