from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "skills/core/design-architecture-reviewer/scripts/design_arch_review.py"
spec = importlib.util.spec_from_file_location("design_arch_review", SCRIPT)
design_arch_review = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(design_arch_review)

SPEC_SCRIPT = Path(__file__).resolve().parents[1] / "skills/core/spec-governor/scripts/spec_governor.py"
spec_governor_spec = importlib.util.spec_from_file_location("spec_governor_for_design_review", SPEC_SCRIPT)
spec_governor = importlib.util.module_from_spec(spec_governor_spec)
assert spec_governor_spec.loader
spec_governor_spec.loader.exec_module(spec_governor)

TECHNICAL_SCRIPT = Path(__file__).resolve().parents[1] / "skills/core/technical-design-governor/scripts/technical_design.py"
technical_spec = importlib.util.spec_from_file_location("technical_design_for_design_review", TECHNICAL_SCRIPT)
technical_design = importlib.util.module_from_spec(technical_spec)
assert technical_spec.loader
technical_spec.loader.exec_module(technical_design)

ARCHITECTURE_SCRIPT = Path(__file__).resolve().parents[1] / "skills/core/architecture-design-governor/scripts/architecture_design.py"
architecture_spec = importlib.util.spec_from_file_location("architecture_design_for_design_review", ARCHITECTURE_SCRIPT)
architecture_design = importlib.util.module_from_spec(architecture_spec)
assert architecture_spec.loader
architecture_spec.loader.exec_module(architecture_design)


def complete_design() -> tuple[dict, dict]:
    architecture_framing = {
        "schema": "codex-architecture-framing-v1",
        "decision": "pass",
        "system_boundary": {
            "decision_type": "modify_existing_system",
            "owner_repo": "web-app",
            "new_service_decision": {
                "required": False,
                "reason": "Checkout discount display reuses the existing pricing contract and only changes web rendering.",
            },
        },
        "repo_responsibilities": [
            {"repo": "web-app", "role": "modify", "responsibility": "render discount rows"},
            {"repo": "pricing-service", "role": "confirm_only", "responsibility": "confirm discounts[] contract"},
        ],
        "runtime_entrypoints": [
            {
                "kind": "frontend_action",
                "trigger": "buyer opens checkout",
                "actor": "buyer browser",
                "repo": "web-app",
                "entrypoint": "src/checkout/usePricing.ts -> src/checkout/CheckoutSummary.tsx",
                "downstream": ["pricing-service GET /api/pricing"],
            }
        ],
        "dependency_graph": {
            "degree": 1,
            "classification": "one_degree_existing_contract",
            "edges": [
                {"from": "web-app", "to": "pricing-service", "interaction": "GET /api/pricing", "change_type": "reuse_existing_contract"}
            ],
        },
        "provider_consumer": [
            {"provider": "pricing-service", "consumer": "web-app", "contract": "pricing response discounts[]", "compatibility": "unchanged"}
        ],
        "data_ownership": [
            {"business_object": "discount", "owner_repo": "pricing-service", "write_authority": "pricing-service", "consumer_rule": "web reads only"}
        ],
        "blockers": [],
    }
    technical = {
        "architecture_framing_ref": "architecture_framing.json",
        "architecture_framing": architecture_framing,
        "design_scope": {"in_scope": ["checkout discount display"], "out_of_scope": ["payment capture"], "assumptions": ["existing API"], "non_goals": ["schema change"]},
        "problem_analysis": {"current_behavior": "web checkout currently renders subtotal and total in src/checkout/CheckoutSummary.tsx from the pricing API", "business_problem": "buyers cannot see discount rows before submitting checkout", "process_gap": "summary render path omits discounts returned by pricing", "code_entrypoints": ["src/checkout/CheckoutSummary.tsx"], "constraints": ["pricing remains server-owned"], "design_goals": ["show discount breakdown"], "non_goals": ["payment capture"], "success_criteria": ["discount rows visible when returned"]},
        "current_state_analysis": {"existing_behavior": "checkout summary already renders subtotal and total from the pricing API response", "code_entrypoints": ["src/checkout/CheckoutSummary.tsx"], "known_constraints": ["pricing remains server-owned"], "reuse_points": ["summary row renderer"]},
        "requirement_trace": [{"requirement_id": "REQ-1", "summary": "show discount breakdown on checkout page"}],
        "business_rule_mapping": [{"requirement_id": "REQ-1", "technical_enforcement": "frontend renders server discount fields", "source_of_truth": "pricing API response"}],
        "process_flow": [{"flow_name": "checkout review", "actors": ["buyer"], "steps": [{"step": 1, "actor": "buyer", "action": "open checkout", "input": "cart", "output": "pricing request starts", "exception": "API error shows fallback"}, {"step": 2, "actor": "web-app", "action": "render discount rows", "input": "pricing response", "output": "discount breakdown", "exception": "missing discounts keep subtotal only"}], "success_end_state": "discount is visible before submit", "failure_end_states": ["pricing unavailable"]}],
        "process_flow_diagram": "```mermaid\nflowchart TD\n    S1[\"1. buyer: open checkout\"]\n    S2[\"2. web-app: render discount rows\"]\n    S1 --> S2\n    S2 --> OK[\"Success: discount is visible before submit\"]\n    S1 -.-> F1[\"Failure: pricing unavailable\"]\n```",
        "module_decomposition": [{"module": "src/checkout/CheckoutSummary.tsx", "responsibility": "render discount rows", "input": "pricing response", "output": "summary UI", "dependencies": ["pricing API"], "cohesion_reason": "presentation only", "coupling_control": "no pricing calculation in UI"}],
        "logical_data_flow": [{"source": "pricing API", "transform": "format discount rows", "destination": "checkout summary", "owner": "pricing-service", "data_security": "no sensitive personal data"}],
        "target_behavior": [{"requirement_id": "REQ-1", "behavior": "buyer sees discount breakdown"}],
        "api_contracts": [{"contract": "discounts[] field unchanged", "compatibility": "additive rendering only", "old_consumer_impact": "none"}],
        "interface_examples": [{"name": "pricing response", "request": "GET /api/pricing", "response": "{\"discounts\":[]}", "error_response": "{\"error\":\"pricing unavailable\"}"}],
        "compatibility_strategy": [{"old_consumer": "checkout page", "old_data": "orders without discounts", "rollback": "hide rows", "behavior": "empty discounts render nothing"}],
        "compatibility_matrix": [{"consumer": "checkout page", "old_behavior": "subtotal only", "new_behavior": "discount rows when present", "compatibility": "additive", "rollback_behavior": "hide rows"}],
        "data_design": [{"read_rule": "read existing discounts array", "write_rule": "no write", "migration": "none"}],
        "data_model_design": {
            "applicable": True,
            "entities": [{"name": "discount", "owner": "pricing-service", "change": "read existing discounts array only"}],
            "field_rules": [{"field": "discounts[]", "type": "array", "nullable": "empty array allowed", "default": "[]"}],
            "ownership": "pricing-service owns discount calculation and field semantics",
            "read_write_rules": {"read": "web-app reads pricing response", "write": "web-app does not write discount data"},
            "migration_strategy": "no schema migration; existing response field only",
            "rollback_strategy": "hide discount rows; no data rollback",
        },
        "table_schema_changes": [{"table": "none", "field": "discounts[] response field", "type": "array", "nullable": "yes", "default": "[]", "migration": "none", "rollback": "none"}],
        "system_interaction_sequence": {
            "applicable": True,
            "participants": ["buyer", "web-app", "pricing-service"],
            "sequence": [
                {"step": 1, "from": "buyer", "to": "web-app", "action": "open checkout", "success": "checkout page loads", "failure": "page remains unavailable", "state_transition": "idle -> loading", "source_evidence": "spec.entrypoints"},
                {"step": 2, "from": "web-app", "to": "pricing-service", "action": "request pricing", "success": "discount payload returns", "failure": "existing pricing error path is shown", "state_transition": "loading -> priced|failed", "source_evidence": "evidence_bundle.contracts"},
                {"step": 3, "from": "pricing-service", "to": "web-app", "action": "return discounts", "success": "discount rows can render", "failure": "web keeps subtotal only", "state_transition": "priced -> rendered|fallback", "source_evidence": "pricing contract"},
            ],
            "timeout_retry": "reuse existing pricing API timeout and retry behavior",
            "idempotency": "read-only pricing request is naturally idempotent",
            "consistency": "pricing-service response is display source of truth",
        },
        "system_sequence_diagram": "```mermaid\nsequenceDiagram\n    autonumber\n    participant buyer\n    participant web-app\n    participant pricing-service\n    buyer->>web-app: open checkout\n    web-app->>pricing-service: request pricing\n    pricing-service->>web-app: return discounts\n```",
        "mq_interactions": [{"applicable": False, "not_applicable_reason": "checkout discount display does not publish or consume asynchronous messages"}],
        "cache_strategy": {"applicable": False, "decision": "no_cache", "reason": "reuse existing pricing request; no new high-frequency aggregate"},
        "transaction_consistency": {"applicable": True, "boundary": "read-only UI render after pricing API response", "idempotency": "GET pricing request", "compensation": "not required for read-only render", "rollback": "revert UI rendering"},
        "observability_design": {"logs": ["existing checkout frontend error log"], "metrics": ["checkout render error count"], "traces": ["pricing request trace id when available"], "alerts": ["checkout JS error alert"]},
        "permission_model": [{"role": "buyer", "rule": "own checkout only", "negative_case": "cannot view other carts"}],
        "exception_and_edge_cases": [{"case": "discounts missing", "handling": "show subtotal only"}],
        "non_functional_requirements": [{"type": "performance", "impact": "no extra request"}],
        "solution_options": [
            {"option_id": "T1", "name": "render existing API field", "description": "UI-only render", "when_to_choose": ["API already returns discounts", "UI-only acceptance"], "implementation_outline": ["read component", "render rows"], "pros": ["small", "safe"], "cons": ["depends on API", "less reusable"], "risk_level": "low", "risk_controls": ["browser regression", "no pricing calc"], "validation": "browser evidence", "test_evidence": ["browser screenshot"], "performance_impact": "none", "rollout_impact": "web only", "rollback_strategy": "revert UI"},
            {"option_id": "T2", "name": "calculate in frontend", "description": "derive discounts in UI", "when_to_choose": ["API cannot change", "temporary display only"], "implementation_outline": ["read pricing data", "calculate rows"], "pros": ["independent", "fast local change"], "cons": ["business logic duplicate", "higher correctness risk"], "risk_level": "high", "risk_controls": ["unit tests", "pricing owner review"], "validation": "unit tests", "test_evidence": ["unit test output"], "performance_impact": "minor CPU", "rollout_impact": "web only", "rollback_strategy": "revert UI"},
        ],
        "option_comparison_matrix": [
            {"criterion": "correctness", "weight": 5, "scores": {"T1": 5, "T2": 2}, "winner": "T1", "reason": "pricing remains source of truth"},
            {"criterion": "blast_radius", "weight": 5, "scores": {"T1": 5, "T2": 4}, "winner": "T1", "reason": "render only"},
            {"criterion": "rollback", "weight": 4, "scores": {"T1": 5, "T2": 5}, "winner": "tie", "reason": "both revert UI"},
            {"criterion": "test_surface", "weight": 4, "scores": {"T1": 4, "T2": 3}, "winner": "T1", "reason": "browser evidence enough"},
        ],
        "option_score_summary": {"T1": 96, "T2": 67, "scoring_rule": "weighted"},
        "selected_solution": {"selected_option_id": "T1", "selection_reason": "keeps pricing source of truth", "decision_criteria": ["correctness", "low coupling"], "tradeoffs": ["UI depends on existing field"], "rejected_alternative_reasoning": [{"option_id": "T2", "reason": "duplicates pricing logic"}]},
        "design_traceability_matrix": [{"requirement_id": "REQ-1", "process_flow_refs": ["checkout review"], "module_refs": ["src/checkout/CheckoutSummary.tsx"], "data_flow_refs": ["pricing API->checkout summary"], "api_contract_refs": ["discounts[]"], "ui_ue_refs": ["checkout summary"], "test_refs": ["UI-1"], "acceptance_refs": ["AC-1"], "selected_option_id": "T1", "decision_reason": "lowest risk"}],
        "acceptance_mapping": [{"acceptance_id": "AC-1", "design_refs": ["checkout summary"], "evidence_required": ["browser screenshot"]}],
        "ui_ue_design": [{"page_or_route": "/checkout", "user_goal": "confirm price", "entry_point": "cart checkout", "layout": "summary panel", "interaction_flow": ["open page"], "states": ["loading", "success", "error"], "field_rules": ["show each discount label and amount"], "permission_visibility": "buyer own cart", "acceptance_evidence": "browser screenshot"}],
        "test_strategy": [{"case": "discount breakdown visible", "evidence": "browser"}],
    }
    architecture = {
        "architecture_framing_ref": "architecture_framing.json",
        "architecture_framing": architecture_framing,
        "architecture_scope": {"in_scope": ["web checkout"], "out_of_scope": ["pricing service"], "assumptions": ["contract exists"], "decision_drivers": ["low coupling"]},
        "current_architecture": {"system_context": "web-app consumes pricing-service during checkout and renders summary data", "repo_entrypoints": ["web-app/src/checkout/CheckoutSummary.tsx"], "upstream_downstream": ["pricing-service -> web-app"], "constraints": ["API remains source of truth"]},
        "architecture_options": [
            {"option_id": "A1", "name": "web only", "description": "render existing contract", "when_to_choose": ["contract exists", "web owns rendering"], "owner_repos": ["web-app"], "confirm_only_repos": ["pricing-service"], "integration_impact": "no new integration", "deployment_impact": "web only", "rollback_complexity": "low", "pros": ["safe", "low coordination"], "cons": ["UI local", "less reusable"], "risk_level": "low", "risk_controls": ["contract confirmation", "browser test"], "validation": "browser", "performance_impact": "none", "rollback_strategy": "revert web"},
            {"option_id": "A2", "name": "pricing API change", "description": "new endpoint", "when_to_choose": ["contract missing", "many consumers need it"], "owner_repos": ["pricing-service", "web-app"], "confirm_only_repos": ["reporting-service"], "integration_impact": "provider consumer test", "deployment_impact": "pricing before web", "rollback_complexity": "medium", "pros": ["explicit", "shared"], "cons": ["contract risk", "ordered release"], "risk_level": "medium", "risk_controls": ["contract freeze", "integration evidence"], "validation": "API+UI", "performance_impact": "extra request", "rollback_strategy": "revert both"},
        ],
        "architecture_fit_matrix": [
            {"criterion": "ownership_clarity", "weight": 5, "scores": {"A1": 5, "A2": 3}, "winner": "A1", "reason": "web owns rendering"},
            {"criterion": "release_coordination", "weight": 5, "scores": {"A1": 5, "A2": 2}, "winner": "A1", "reason": "web only"},
            {"criterion": "contract_risk", "weight": 5, "scores": {"A1": 5, "A2": 2}, "winner": "A1", "reason": "contract unchanged"},
            {"criterion": "rollback", "weight": 4, "scores": {"A1": 5, "A2": 3}, "winner": "A1", "reason": "single repo"},
        ],
        "architecture_score_summary": {"A1": 95, "A2": 70, "scoring_rule": "weighted"},
        "selected_architecture": {"selected_option_id": "A1", "selection_reason": "no API change", "decision_criteria": ["compatibility", "low coupling"], "tradeoffs": ["UI renders existing data"], "rejected_alternative_reasoning": [{"option_id": "A2", "reason": "adds contract risk"}]},
        "architecture_traceability_matrix": [{"requirement_id": "REQ-1", "component_boundary_refs": ["web-app owns rendering"], "module_topology_refs": ["web-app/checkout-summary"], "data_flow_refs": ["pricing-service->web-app"], "integration_sequence_refs": ["checkout load"], "contract_refs": ["discounts[]"], "selected_architecture_option_id": "A1", "decision_reason": "lowest integration risk"}],
        "component_boundaries": [{"component": "web-app", "role": "render", "exclusion": "no pricing calculation"}],
        "module_topology": [{"repo": "web-app", "module": "checkout-summary", "responsibility": "display", "depends_on": ["pricing-service"], "boundary_rule": "read-only API consumer", "change_type": "modify"}],
        "repo_responsibilities": [{"repo": "web-app", "role": "modify", "responsibility": "render discount rows"}, {"repo": "pricing-service", "role": "confirm_only", "responsibility": "contract unchanged"}],
        "cross_repo_contracts": [{"producer": "pricing-service", "consumer": "web-app", "contract": "discounts[]", "compatibility": "unchanged", "failure_mode": "empty discounts render none"}],
        "cross_repo_dependency_graph": [{"from": "pricing-service", "to": "web-app", "contract": "discounts[]", "change": "confirm only"}],
        "data_flow": [{"source": "pricing-service", "target": "web-app", "rule": "display only"}],
        "data_ownership": [{"business_object": "discount", "owner_repo": "pricing-service", "write_authority": "pricing-service", "consistency_rule": "web read only"}],
        "integration_sequence": [{"step": 1, "actor": "web-app", "target": "pricing-service", "action": "load pricing", "failure_handling": "show existing error"}],
        "integration_sequence_diagram": "```mermaid\nsequenceDiagram\n    autonumber\n    participant web-app\n    participant pricing-service\n    web-app->>pricing-service: load pricing\n```",
        "failure_isolation": [{"failure": "discounts omitted", "isolation": "render subtotal only", "user_impact": "checkout continues"}],
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
    }
    return technical, architecture


def test_reviewer_accepts_explicitly_excluded_api_examples_and_data_design() -> None:
    technical, architecture = complete_design()
    technical["impact_applicability"] = [
        {"area": "api", "status": "excluded", "reason": "existing contract unchanged"},
        {"area": "data", "status": "excluded", "reason": "no persistence change"},
        {"area": "ui", "status": "required", "reason": "frontend behavior changes"},
    ]
    technical["interface_examples"] = []
    technical["data_design"] = []
    technical["data_model_design"] = {
        "applicable": False,
        "not_applicable_reason": "The change only updates frontend runtime state and does not alter entities, tables, fields, or persisted values.",
    }
    result = design_arch_review.review(technical, architecture)
    review_findings = result["api_contract_review"] + result["data_model_review"]
    assert not any(item["message"] == "API/interface examples are missing" for item in review_findings)
    assert not any(item["message"] == "data design is missing" for item in review_findings)


def test_thin_design_blocks() -> None:
    result = design_arch_review.review({"requirement_trace": [{"requirement_id": "REQ-1"}]}, {})
    assert result["schema"] == "codex-design-architecture-review-v1"
    assert result["decision"] == "block"
    assert result["score"] < 60
    assert not result["readiness_gate"]["implementation_allowed"]


def test_unclear_requirement_understanding_blocks_design_review() -> None:
    unclear_spec = spec_governor.normalize("REQ-AMB", "Ambiguous Renewal", "优化续费流程，状态更新正确，功能正常。")
    technical = technical_design.render(unclear_spec)
    architecture = architecture_design.render(unclear_spec, technical)
    result = design_arch_review.review(technical, architecture)
    assert technical["requirements_understanding_gate"]["design_allowed"] is False
    assert architecture["requirements_understanding_gate"]["design_allowed"] is False
    assert result["decision"] == "block"
    assert not result["readiness_gate"]["implementation_allowed"]
    messages = json_dumps(result)
    assert "requirement understanding gate blocks design" in messages
    assert "business_flow" in messages
    assert "entrypoints" in messages


def test_clear_requirement_understanding_gate_passes_through_designs() -> None:
    clear_source = """
业务目的: 减少运营手工核对续费状态的时间。
流程: 运营在续费列表点击重新试算按钮，系统调用续费试算接口并刷新当前设备的试算结果。
入口: 续费列表的重新试算按钮。
Req: 运营可以对单个设备重新触发续费试算。
Rule: 只有有续费管理权限的运营角色可以触发。
AC: 给定有权限运营在续费列表点击重新试算按钮，接口返回成功后页面展示新的试算金额和试算时间。
AC: 无权限角色看不到重新试算按钮且直接调用接口返回无权限。
"""
    clear_spec = spec_governor.normalize("REQ-CLEAR", "Renewal Requote", clear_source)
    technical = technical_design.render(clear_spec)
    architecture = architecture_design.render(clear_spec, technical)
    assert clear_spec["design_allowed"] is True
    assert technical["requirements_understanding_gate"]["design_allowed"] is True
    assert technical["requirements_understanding_gate"]["business_intent"]
    assert technical["requirements_understanding_gate"]["business_flow"]
    assert technical["requirements_understanding_gate"]["entrypoints"]
    assert "business_closure_model" in technical["requirements_understanding_gate"]
    assert "state_machine" in technical["requirements_understanding_gate"]
    assert "dependency_chain" in technical["requirements_understanding_gate"]
    assert architecture["requirements_understanding_gate"]["design_allowed"] is True
    assert "business_closure_model" in architecture["requirements_understanding_gate"]


def test_complete_design_passes() -> None:
    technical, architecture = complete_design()
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "pass"
    assert result["score"] >= 85
    assert result["readiness_gate"]["implementation_allowed"]
    valid, issues = design_arch_review.validate(result)
    assert valid, issues


def test_missing_design_diagrams_block_review() -> None:
    technical, architecture = complete_design()
    technical["process_flow_diagram"] = ""
    technical["system_sequence_diagram"] = ""
    architecture["integration_sequence_diagram"] = ""

    result = design_arch_review.review(technical, architecture)
    messages = json_dumps(result)

    assert result["decision"] == "block"
    assert "process flow diagram is missing" in messages
    assert "system sequence diagram is missing" in messages
    assert "integration sequence diagram is missing" in messages


def test_specialty_blocker_is_aggregated_and_blocks_implementation() -> None:
    technical, architecture = complete_design()
    result = design_arch_review.review(
        technical,
        architecture,
        specialty_artifacts={
            "data_security_review.json": {
                "decision": "needs_review",
                "blockers": [{"message": "tenant isolation is undefined"}],
            }
        },
    )
    assert result["decision"] == "block"
    assert result["readiness_gate"]["implementation_allowed"] is False
    assert result["specialty_review_summary"][0]["artifact"] == "data_security_review.json"
    assert result["input_digests"]["technical_design.json"]


def test_missing_option_comparison_needs_revision() -> None:
    technical, architecture = complete_design()
    technical["option_comparison_matrix"] = []
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "needs_revision"
    assert not result["readiness_gate"]["implementation_allowed"]
    assert result["severity_counts"]["high"] >= 1


def test_thin_option_details_need_revision() -> None:
    technical, architecture = complete_design()
    technical["solution_options"][0].pop("when_to_choose")
    architecture["architecture_options"][0].pop("deployment_impact")
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "needs_revision"
    assert not result["readiness_gate"]["implementation_allowed"]
    messages = json_dumps(result)
    assert "option lacks required fields" in messages


def test_missing_rejected_alternative_reasoning_needs_revision() -> None:
    technical, architecture = complete_design()
    technical["selected_solution"].pop("rejected_alternative_reasoning")
    architecture["selected_architecture"].pop("rejected_alternative_reasoning")
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "needs_revision"
    assert not result["readiness_gate"]["implementation_allowed"]
    messages = json_dumps(result)
    assert "rejected alternative reasoning" in messages


def test_generic_design_phrasing_needs_revision() -> None:
    technical, architecture = complete_design()
    technical["module_decomposition"][0]["module"] = "target module to be confirmed"
    architecture["cross_repo_contracts"][0]["producer"] = "existing producer"
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "needs_revision"
    assert "generic template phrasing" in json_dumps(result)


def test_template_problem_analysis_needs_revision() -> None:
    technical, architecture = complete_design()
    technical.pop("problem_analysis")
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "needs_revision"
    assert "problem_analysis is missing" in json_dumps(result)


def test_standalone_readability_needs_revision_without_current_state_and_proof() -> None:
    technical, architecture = complete_design()
    technical.pop("problem_analysis")
    technical.pop("current_state_analysis")
    technical.pop("acceptance_mapping")
    technical.pop("design_traceability_matrix")
    architecture.pop("current_architecture")
    architecture.pop("component_boundaries")
    result = design_arch_review.review(technical, architecture)
    messages = json_dumps(result)
    assert "design cannot be understood standalone" in messages
    assert "current_state" in messages
    assert "satisfaction_proof" in messages


def test_template_option_decision_needs_revision() -> None:
    technical, architecture = complete_design()
    technical["solution_options"][0]["name"] = "Minimal scoped change"
    technical["selected_solution"]["selection_reason"] = "Default to smallest safe change because it has lower blast radius."
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "needs_revision"
    messages = json_dumps(result)
    assert "template option" in messages or "template rationale" in messages


def test_selected_option_must_match_highest_score() -> None:
    technical, architecture = complete_design()
    technical["selected_solution"]["selected_option_id"] = "T2"
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "needs_revision"
    assert "does not match highest weighted score" in json_dumps(result)


def test_low_confidence_generic_entrypoint_needs_revision() -> None:
    technical, architecture = complete_design()
    technical["code_entrypoint_confidence"] = {
        "level": "low",
        "selected_entrypoint": "src/assets/icons/index.js",
        "evidence": ["generic_entrypoint_penalty"],
    }
    technical["module_decomposition"][0]["module"] = "src/assets/icons/index.js"
    architecture["code_entrypoint_confidence"] = technical["code_entrypoint_confidence"]
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "needs_revision"
    messages = json_dumps(result)
    assert "primary code entrypoint confidence is low" in messages
    assert "generic bootstrap/config/asset file" in messages


def test_rejected_source_candidate_blocks_design_even_with_high_confidence() -> None:
    technical, architecture = complete_design()
    evidence = {
        "schema": "codex-source-location-evidence-v1",
        "decision": "pass",
        "confirmed_anchors": [{"path": "src/views/plugIn/accidentAnalysis.vue", "confidence": "high"}],
        "rejected_candidates": [{"path": "src/views/device/replacementSettlement.vue", "reason": "weak device-only match"}],
    }
    technical["source_location_evidence"] = evidence
    architecture["source_location_evidence"] = evidence
    technical["code_entrypoint_confidence"] = {
        "level": "high",
        "selected_entrypoint": "src/views/device/replacementSettlement.vue",
        "evidence": ["manually_marked_high"],
    }
    architecture["code_entrypoint_confidence"] = technical["code_entrypoint_confidence"]
    technical["module_decomposition"][0]["module"] = "src/views/device/replacementSettlement.vue"
    architecture["module_topology"][0]["module"] = "src/views/device/replacementSettlement.vue"
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] in {"needs_revision", "block"}
    messages = json_dumps(result)
    assert "selected entrypoint is not a confirmed source anchor" in messages
    assert "rejected source candidates leaked" in messages


def test_rejected_source_candidate_in_sequence_blocks_design() -> None:
    technical, architecture = complete_design()
    evidence = {
        "decision": "pass",
        "confirmed_anchors": [{"path": "src/checkout/CheckoutSummary.tsx", "confidence": "high"}],
        "rejected_candidates": [{"path": "src/device/iotPoolMonitor.vue", "reason": "weak match"}],
    }
    technical["source_location_evidence"] = evidence
    architecture["source_location_evidence"] = evidence
    technical["system_interaction_sequence"]["participants"].append("src/device/iotPoolMonitor.vue")
    technical["system_interaction_sequence"]["sequence"].append({
        "from": "src/checkout/CheckoutSummary.tsx",
        "to": "src/device/iotPoolMonitor.vue",
        "action": "wrong inferred call",
    })
    result = design_arch_review.review(technical, architecture)
    assert "rejected source candidates leaked" in json_dumps(result)


def test_complex_breakdown_flattened_to_one_module_needs_revision() -> None:
    technical, architecture = complete_design()
    technical["requirement_breakdown"] = [
        {"id": f"BRK-{idx}", "summary": f"business slice {idx}", "behavior_change": f"change {idx}", "impact_areas": ["data"], "field_impact": "field", "api_impact": "api", "permission_impact": "permission"}
        for idx in range(1, 5)
    ]
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "needs_revision"
    assert "flattened into one module row" in json_dumps(result)


def test_complex_breakdown_with_confident_entrypoint_passes() -> None:
    technical, architecture = complete_design()
    technical["requirement_breakdown"] = [
        {"id": f"BRK-{idx}", "summary": f"business slice {idx}", "behavior_change": f"change {idx}", "impact_areas": ["ui"], "field_impact": "no field", "api_impact": "no api", "permission_impact": "preserve permission"}
        for idx in range(1, 4)
    ]
    technical["code_entrypoint_confidence"] = {
        "level": "high",
        "selected_entrypoint": "src/checkout/CheckoutSummary.tsx",
        "evidence": ["checkout", "semantic_match", "feature"],
    }
    technical["module_decomposition"] = [
        {**technical["module_decomposition"][0], "responsibility": item["summary"], "requirement_breakdown_id": item["id"]}
        for item in technical["requirement_breakdown"]
    ]
    architecture["code_entrypoint_confidence"] = technical["code_entrypoint_confidence"]
    architecture["module_topology"] = [
        {**architecture["module_topology"][0], "responsibility": item["summary"], "requirement_breakdown_id": item["id"]}
        for item in technical["requirement_breakdown"]
    ]
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "pass"


def test_mq_design_requires_upstream_downstream_trigger_and_recovery() -> None:
    technical, architecture = complete_design()
    technical["mq_interactions"] = [{
        "applicable": True,
        "producer": "payment-service",
        "consumer": "dashboard-service",
        "topic_or_queue": "payment.failure.changed",
        "payload_fields": ["payment_id"],
    }]
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "block"
    assert "MQ interaction lacks production-grade fields" in json_dumps(result)


def test_cache_use_requires_key_ttl_invalidation_and_consistency_risk() -> None:
    technical, architecture = complete_design()
    technical["cache_strategy"] = {"applicable": True, "decision": "use_cache", "key_design": "dashboard:{tenant_id}"}
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "needs_revision"
    assert "cache strategy chooses cache without required safeguards" in json_dumps(result)


def test_data_model_requires_table_schema_details_when_applicable() -> None:
    technical, architecture = complete_design()
    technical["data_model_design"] = {"applicable": True, "entities": [{"name": "discount"}]}
    technical["table_schema_changes"] = [{"table": "discount_record", "field": "discount_amount"}]
    result = design_arch_review.review(technical, architecture)
    messages = json_dumps(result)
    assert result["decision"] == "needs_revision"
    assert "data_model_design lacks required details" in messages
    assert "table schema change lacks implementation-grade fields" in messages


def test_new_service_signal_requires_new_service_design() -> None:
    technical, architecture = complete_design()
    architecture["architecture_scope"]["in_scope"] = ["create new notification service"]
    architecture["architecture_options"][0]["name"] = "create notification-service"
    result = design_arch_review.review(technical, architecture)
    assert result["decision"] == "block"
    assert "new service requirement lacks new_service_design" in json_dumps(result)


def test_new_service_design_requires_bootstrap_operations_and_ownership() -> None:
    technical, architecture = complete_design()
    architecture["new_service_design"] = {
        "creation_reason": "new service needed",
        "existing_system_fit_analysis": {"reuse_candidates": ["identity-service"]},
    }
    result = design_arch_review.review(technical, architecture)
    messages = json_dumps(result)
    assert result["decision"] == "block"
    assert "new_service_design lacks expert-grade fields" in messages
    assert "new service creation reason is too shallow" in messages


def json_dumps(value: dict) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


def run_all() -> None:
    test_thin_design_blocks()
    test_complete_design_passes()
    test_missing_option_comparison_needs_revision()
    test_thin_option_details_need_revision()
    test_missing_rejected_alternative_reasoning_needs_revision()
    test_generic_design_phrasing_needs_revision()
    test_template_problem_analysis_needs_revision()
    test_template_option_decision_needs_revision()
    test_selected_option_must_match_highest_score()
    test_low_confidence_generic_entrypoint_needs_revision()
    test_complex_breakdown_flattened_to_one_module_needs_revision()
    test_complex_breakdown_with_confident_entrypoint_passes()
    test_new_service_signal_requires_new_service_design()
    test_new_service_design_requires_bootstrap_operations_and_ownership()


if __name__ == "__main__":
    run_all()
    print("PASS design_architecture_reviewer tests")
