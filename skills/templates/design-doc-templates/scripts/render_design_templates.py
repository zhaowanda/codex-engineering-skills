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
        "mq_interactions": [],
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
        "new_service_design": {},
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
        "problem_analysis": {
            "current_behavior": "Checkout already calls GET /api/pricing through usePricing and renders subtotal and total in CheckoutSummary, but it does not expose the returned discount breakdown to the buyer.",
            "business_problem": "Buyers cannot verify coupon or promotion discounts before order submission, which creates checkout support questions even though pricing-service already owns the discount calculation.",
            "process_gap": "The frontend has the pricing response available but drops discounts[] during summary rendering; no backend price calculation or persistence path needs to change.",
            "code_entrypoints": ["src/checkout/CheckoutSummary.tsx", "src/checkout/usePricing.ts"],
            "constraints": ["pricing-service remains the source of truth", "no additional checkout request", "render missing discounts as empty state"],
            "design_goals": ["render discount label and amount before submit", "preserve existing pricing API compatibility", "avoid duplicating pricing logic in web"],
            "success_criteria": ["discount rows display when discounts[] is present", "orders without discounts render the previous subtotal/total view", "browser regression and checkout test evidence pass"],
        },
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
        "data_model_design": {
            "applicable": False,
            "not_applicable_reason": "The change reads the existing pricing response discounts[] field for display only and does not add, remove, backfill, or persist any entity/table/field.",
        },
        "system_interaction_sequence": {
            "applicable": True,
            "participants": ["buyer browser", "web-app checkout page", "pricing-service"],
            "sequence": [
                {"step": 1, "from": "buyer browser", "to": "web-app checkout page", "action": "open /checkout and trigger usePricing"},
                {"step": 2, "from": "web-app checkout page", "to": "pricing-service", "action": "GET /api/pricing?cartId={cartId}"},
                {"step": 3, "from": "pricing-service", "to": "web-app checkout page", "action": "return subtotal, total, and discounts[]"},
                {"step": 4, "from": "web-app checkout page", "to": "buyer browser", "action": "render discount rows without recalculating prices"},
            ],
            "timeout_retry": "Preserve existing usePricing timeout and retry behavior; no new retry loop is introduced for discount rendering.",
            "idempotency": "Read-only pricing query remains idempotent and the UI render has no side effect.",
            "consistency": "Discount display uses the same pricing response snapshot as subtotal and total, so rows cannot drift from the displayed total.",
        },
        "mq_interactions": [
            {
                "applicable": False,
                "not_applicable_reason": "Checkout discount display only handles the browser submit event and does not publish or consume asynchronous MQ messages.",
            }
        ],
        "transaction_consistency": {
            "applicable": False,
            "not_applicable_reason": "The selected solution is read-only UI rendering and does not introduce database writes, distributed transactions, or compensating updates.",
        },
        "observability_design": {
            "logs": "Reuse existing frontend error logging for pricing load failures; do not log cart contents or discount payload values.",
            "metrics": "Reuse checkout page error-rate and render-failure counters; no new backend metric is required for a display-only change.",
            "traces": "Keep existing pricing request trace correlation from web-app to pricing-service.",
            "alerts": "Existing checkout JS error alert remains sufficient; rollback if error rate increases after rollout.",
        },
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


def new_service_example_technical(doc_id: str, title: str) -> dict[str, Any]:
    data = example_technical(doc_id, title)
    data["design_scope"] = {
        "in_scope": ["create notification-service for customer notification preferences"],
        "out_of_scope": ["migrate historical notification delivery logs"],
        "assumptions": ["identity-service already owns user identity", "existing monolith exposes read-only customer profile APIs"],
        "non_goals": ["replace email provider in first release"],
    }
    data["problem_analysis"] = {
        "current_behavior": "The commerce monolith stores customer notification preferences inside account settings and exposes them only through internal account modules.",
        "business_problem": "Upcoming SMS, email, and in-app notification channels need independent preference APIs and audit controls; adding this to the monolith would increase account-module coupling and release risk.",
        "process_gap": "No service currently owns channel preference lifecycle, consent audit, or provider-independent preference reads for downstream notification senders.",
        "code_entrypoints": ["monolith/account/preferences", "identity-service/users"],
        "constraints": ["identity-service remains user source of truth", "notification-service owns only preferences and consent audit", "first release must support compatible read path from monolith"],
        "design_goals": ["bootstrap notification-service", "expose preference read/write APIs", "keep monolith as compatibility consumer during migration"],
        "success_criteria": ["new service deploys with CI/CD baseline", "preference APIs pass contract tests", "monolith can read preferences through compatibility adapter"],
    }
    data["current_state_analysis"] = {
        "existing_behavior": "Preference reads are embedded in monolith account settings, while identity-service owns user identity and downstream notification senders cannot query channel consent independently.",
        "code_entrypoints": ["monolith/account/preferences", "identity-service/users"],
        "known_constraints": ["identity remains outside the new service", "first release cannot break monolith account settings"],
        "reuse_points": ["identity-service user id contract", "existing account preference DTO semantics"],
    }
    data["requirement_trace"] = [{"requirement_id": "REQ-NEW-SVC", "summary": "create notification-service for customer notification preferences"}]
    data["business_rule_mapping"] = [{"requirement_id": "REQ-NEW-SVC", "technical_enforcement": "notification-service owns preference write APIs and consent audit", "source_of_truth": "notification-service preference store"}]
    data["process_flow"] = [{"flow_name": "preference update", "actors": ["customer", "account frontend", "notification-service"], "steps": [{"step": 1, "actor": "customer", "action": "save notification preference", "input": "channel consent", "output": "updated preference", "exception": "invalid channel returns validation error"}], "success_end_state": "preference and audit record are persisted", "failure_end_states": ["identity lookup failed", "validation failed"]}]
    data["module_decomposition"] = [
        {"module": "notification-service/src/main/java/com/example/notification/api/PreferenceController.java", "responsibility": "own preference REST API", "input": "preference request DTO", "output": "preference response DTO", "dependencies": ["PreferenceService", "identity-service client"], "cohesion_reason": "API layer only maps HTTP contract", "coupling_control": "business rules stay in service/domain layer"},
        {"module": "notification-service/src/main/java/com/example/notification/domain/PreferenceService.java", "responsibility": "validate channel consent and write audit trail", "input": "user id and channel preference", "output": "stored preference", "dependencies": ["PreferenceRepository", "ConsentAuditRepository"], "cohesion_reason": "single owner for preference lifecycle", "coupling_control": "identity-service is read-only dependency"},
    ]
    data["logical_data_flow"] = [{"source": "account frontend", "transform": "validate user id and channel preference", "destination": "notification-service preference store", "owner": "notification-service", "data_security": "tenant/user scope and consent audit required"}]
    data["target_behavior"] = [{"requirement_id": "REQ-NEW-SVC", "behavior": "customers and monolith compatibility adapter use notification-service APIs for preference reads and writes"}]
    data["api_contracts"] = [
        {"endpoint": "POST /api/notification/preferences", "request": "PreferenceUpdateRequest", "response": "PreferenceResponse", "compatibility": "new additive provider API", "old_consumer_impact": "monolith migrates through adapter without account UI contract break"},
        {"endpoint": "GET /api/notification/preferences/{userId}", "request": "userId path parameter", "response": "PreferenceResponse", "compatibility": "new read API for downstream senders", "old_consumer_impact": "none for first release"},
    ]
    data["interface_examples"] = [{"name": "update preference", "request": "POST /api/notification/preferences {\"userId\":\"u-1\",\"channel\":\"SMS\",\"enabled\":true}", "response": "{\"userId\":\"u-1\",\"preferences\":[{\"channel\":\"SMS\",\"enabled\":true}]}", "error_response": "{\"code\":\"INVALID_CHANNEL\"}"}]
    data["compatibility_strategy"] = [{"old_consumer": "monolith account settings", "old_data": "existing account preference fields", "rollback": "route account settings back to monolith fields", "behavior": "adapter reads new service only after cutover flag"}]
    data["compatibility_matrix"] = [{"consumer": "monolith account settings", "old_behavior": "local preference read/write", "new_behavior": "adapter calls notification-service", "compatibility": "flag controlled", "rollback_behavior": "disable adapter flag"}]
    data["data_design"] = [{"read_rule": "read preferences by user_id and tenant_id", "write_rule": "write preference plus consent audit in one service transaction", "migration": "first release dual-read disabled until backfill plan is approved"}]
    data["data_model_design"] = {
        "applicable": True,
        "entities": [{"name": "notification_preference", "owner": "notification-service"}, {"name": "notification_consent_audit", "owner": "notification-service"}],
        "field_rules": [{"field": "user_id", "type": "string", "nullable": "no"}, {"field": "channel", "type": "enum", "nullable": "no"}, {"field": "enabled", "type": "boolean", "nullable": "no"}],
        "ownership": "notification-service owns preference and consent audit; identity-service owns user profile",
        "read_write_rules": {"read": "scope by tenant_id and user_id", "write": "validate channel and write audit in same transaction"},
        "migration_strategy": "create new tables before traffic cutover; no historical delivery log migration in first release",
        "rollback_strategy": "disable traffic flag and keep new tables dormant; no destructive rollback required",
    }
    data["table_schema_changes"] = [{"table": "notification_preference", "field": "user_id/channel/enabled", "type": "varchar/enum/boolean", "nullable": "no", "default": "enabled defaults false", "migration": "create table before service deploy", "rollback": "stop traffic and leave table for later cleanup"}]
    data["system_interaction_sequence"] = {
        "applicable": True,
        "participants": ["account frontend", "monolith account adapter", "notification-service", "identity-service", "notification database"],
        "sequence": [
            {"step": 1, "from": "account frontend", "to": "monolith account adapter", "action": "save notification preference"},
            {"step": 2, "from": "monolith account adapter", "to": "notification-service", "action": "POST /api/notification/preferences"},
            {"step": 3, "from": "notification-service", "to": "identity-service", "action": "validate user id and tenant scope"},
            {"step": 4, "from": "notification-service", "to": "notification database", "action": "write preference and consent audit"},
        ],
        "timeout_retry": "monolith adapter uses existing API timeout; write retries require idempotency key",
        "idempotency": "preference update idempotency key is user_id + channel + request_id",
        "consistency": "preference and consent audit are committed in one notification-service transaction",
    }
    data["transaction_consistency"] = {"applicable": True, "boundary": "notification-service writes preference and audit record in one local transaction", "idempotency": "request_id per update", "compensation": "manual replay from audit request log if downstream adapter times out after commit", "rollback": "disable adapter traffic and keep committed preferences as dormant data"}
    data["permission_model"] = [{"role": "customer", "rule": "may update only own preferences within tenant scope", "negative_case": "cross-tenant user id is rejected"}]
    data["exception_and_edge_cases"] = [{"case": "identity-service unavailable", "handling": "return dependency unavailable and do not write preference"}, {"case": "duplicate request_id", "handling": "return previous successful result"}]
    data["non_functional_requirements"] = [{"type": "performance", "impact": "single identity read and two local writes per update"}, {"type": "security", "impact": "tenant scoped API and consent audit"}]
    data["solution_options"] = [
        {"option_id": "T1", "name": "new notification-service owns preferences", "description": "bootstrap a dedicated service for preference lifecycle and consent audit", "when_to_choose": ["multiple consumers need preference APIs", "monolith ownership would increase account coupling"], "implementation_outline": ["create service scaffold", "add preference APIs", "add monolith adapter", "deploy behind traffic flag"], "pros": ["clear ownership", "independent release path"], "cons": ["new operational surface", "requires bootstrap and oncall"], "risk_level": "medium", "risk_controls": ["contract tests", "traffic flag", "runbook"], "validation": "API contract, integration, and deployment smoke tests", "test_evidence": ["API tests", "monolith adapter integration", "CI/CD proof"], "performance_impact": "one new service hop for migrated reads/writes", "rollout_impact": "new deployable plus monolith adapter", "rollback_strategy": "disable adapter flag and route to monolith"},
        {"option_id": "T2", "name": "extend monolith account module", "description": "keep preferences inside monolith account settings", "when_to_choose": ["only account UI needs preferences", "no independent sender consumers"], "implementation_outline": ["add monolith fields", "extend account APIs"], "pros": ["fastest first change", "no new deployable"], "cons": ["keeps sender consumers coupled to account module", "harder consent audit ownership"], "risk_level": "medium", "risk_controls": ["module boundaries", "account regression"], "validation": "monolith tests", "test_evidence": ["account API tests"], "performance_impact": "no new hop", "rollout_impact": "monolith deploy only", "rollback_strategy": "revert account module"},
    ]
    data["option_comparison_matrix"] = [
        {"criterion": "ownership_clarity", "weight": 5, "scores": {"T1": 5, "T2": 2}, "winner": "T1", "reason": "dedicated lifecycle and audit owner"},
        {"criterion": "consumer_scalability", "weight": 5, "scores": {"T1": 5, "T2": 2}, "winner": "T1", "reason": "senders can consume stable preference APIs"},
        {"criterion": "operational_cost", "weight": 4, "scores": {"T1": 3, "T2": 5}, "winner": "T2", "reason": "new service has bootstrap cost"},
        {"criterion": "rollback_safety", "weight": 4, "scores": {"T1": 4, "T2": 4}, "winner": "tie", "reason": "both can be flag or code reverted"},
    ]
    data["option_score_summary"] = {"T1": 88, "T2": 68, "scoring_rule": "weighted new-service fit score"}
    data["selected_solution"] = {"selected_option_id": "T1", "selection_reason": "The requirement creates an independent preference lifecycle and multiple consumers, so new service ownership is justified despite bootstrap cost.", "decision_criteria": ["ownership clarity", "consumer scalability", "auditability"], "tradeoffs": ["adds operational surface and CI/CD setup"], "rejected_alternative_reasoning": [{"option_id": "T2", "reason": "monolith extension does not provide independent preference ownership for sender consumers"}]}
    data["design_traceability_matrix"] = [{"requirement_id": "REQ-NEW-SVC", "process_flow_refs": ["preference update"], "module_refs": ["PreferenceController", "PreferenceService"], "data_flow_refs": ["account frontend->notification-service"], "api_contract_refs": ["POST /api/notification/preferences"], "ui_ue_refs": ["account settings"], "test_refs": ["API-1", "INT-1"], "acceptance_refs": ["AC-NEW-SVC-1"], "selected_option_id": "T1", "decision_reason": "best ownership and consumer scalability"}]
    data["acceptance_mapping"] = [{"acceptance_id": "AC-NEW-SVC-1", "design_refs": ["notification-service APIs", "monolith adapter"], "evidence_required": ["service CI", "API contract tests", "adapter integration tests"]}]
    data["ui_ue_design"] = [{"page_or_route": "/account/preferences", "user_goal": "save notification channel preferences", "entry_point": "account settings notification tab", "layout": "existing account settings form", "interaction_flow": ["toggle channel", "save", "show success"], "states": ["loading", "success", "validation error", "dependency error"], "field_rules": ["channel enum only", "tenant scoped user id"], "permission_visibility": "customer own account only", "acceptance_evidence": "browser or API integration evidence"}]
    data["test_strategy"] = [{"summary": "service API, adapter integration, CI/CD, and rollback flag evidence required", "evidence": ["mvn test", "contract test", "adapter integration"], "test_design_ref": "test_design.json"}]
    return data


def new_service_example_architecture(doc_id: str, title: str) -> dict[str, Any]:
    data = example_architecture(doc_id, title)
    data["architecture_scope"] = {"in_scope": ["new notification-service", "monolith compatibility adapter"], "out_of_scope": ["replace downstream senders in first release"], "assumptions": ["identity-service user contract exists"], "decision_drivers": ["clear ownership", "auditable consent", "controlled migration"]}
    data["current_architecture"] = {"system_context": "monolith account module owns preference UI and persistence today, identity-service owns user identity, and sender services lack independent preference APIs", "repo_entrypoints": ["monolith/account/preferences", "identity-service/users"], "upstream_downstream": ["account frontend -> monolith", "monolith -> identity-service"], "constraints": ["monolith compatibility must remain during first release"]}
    data["architecture_options"] = [
        {"option_id": "A1", "name": "create notification-service", "description": "new service owns preference lifecycle and consent audit", "when_to_choose": ["multiple consumers need preference APIs", "audit ownership must be isolated"], "owner_repos": ["notification-service", "monolith"], "confirm_only_repos": ["identity-service"], "integration_impact": "new provider API plus monolith adapter", "deployment_impact": "deploy notification-service before enabling monolith adapter flag", "rollback_complexity": "medium", "pros": ["clear ownership", "independent scaling"], "cons": ["new operations baseline", "new service hop"], "risk_level": "medium", "risk_controls": ["traffic flag", "contract tests", "runbook"], "validation": "service smoke, contract, and adapter integration", "performance_impact": "one new API hop", "rollback_strategy": "disable adapter flag"},
        {"option_id": "A2", "name": "keep preferences in monolith", "description": "extend existing account module", "when_to_choose": ["single consumer remains account UI", "no independent audit owner needed"], "owner_repos": ["monolith"], "confirm_only_repos": ["identity-service"], "integration_impact": "no new provider", "deployment_impact": "monolith deploy only", "rollback_complexity": "low", "pros": ["lower bootstrap cost", "fewer deployables"], "cons": ["continued coupling", "weaker ownership"], "risk_level": "medium", "risk_controls": ["module boundary review", "account regression"], "validation": "monolith tests", "performance_impact": "no new hop", "rollback_strategy": "revert monolith"},
    ]
    data["architecture_fit_matrix"] = [
        {"criterion": "ownership_clarity", "weight": 5, "scores": {"A1": 5, "A2": 2}, "winner": "A1", "reason": "new service owns preference lifecycle"},
        {"criterion": "consumer_scalability", "weight": 5, "scores": {"A1": 5, "A2": 2}, "winner": "A1", "reason": "provider API supports multiple consumers"},
        {"criterion": "bootstrap_cost", "weight": 4, "scores": {"A1": 3, "A2": 5}, "winner": "A2", "reason": "monolith has lower initial cost"},
        {"criterion": "rollback", "weight": 4, "scores": {"A1": 4, "A2": 4}, "winner": "tie", "reason": "both have clear rollback"},
    ]
    data["architecture_score_summary"] = {"A1": 88, "A2": 68, "scoring_rule": "weighted architecture fit score"}
    data["selected_architecture"] = {"selected_option_id": "A1", "selection_reason": "New service is selected because preference ownership, consent audit, and multiple consumers outweigh bootstrap cost.", "decision_criteria": ["ownership", "consumer scalability", "auditability"], "tradeoffs": ["adds CI/CD and operational baseline"], "rejected_alternative_reasoning": [{"option_id": "A2", "reason": "monolith ownership does not scale to downstream sender consumers"}]}
    data["architecture_traceability_matrix"] = [{"requirement_id": "REQ-NEW-SVC", "component_boundary_refs": ["notification-service owns preferences"], "module_topology_refs": ["notification-service/api", "notification-service/domain", "monolith adapter"], "data_flow_refs": ["monolith->notification-service"], "integration_sequence_refs": ["preference update"], "contract_refs": ["POST /api/notification/preferences"], "selected_architecture_option_id": "A1", "decision_reason": "clear service ownership"}]
    data["component_boundaries"] = [{"component": "notification-service", "role": "own preference lifecycle and consent audit", "exclusion": "does not own user identity or delivery provider execution"}, {"component": "monolith", "role": "compatibility adapter and account UI", "exclusion": "does not remain long-term source of truth"}]
    data["module_topology"] = [{"repo": "notification-service", "module": "api/domain/repository/config", "responsibility": "preference APIs, validation, persistence, audit, configuration", "depends_on": ["identity-service", "notification database"], "boundary_rule": "identity read-only, preference writes local", "change_type": "create"}, {"repo": "monolith", "module": "account/preferences adapter", "responsibility": "route account UI calls to notification-service under flag", "depends_on": ["notification-service"], "boundary_rule": "compatibility adapter only", "change_type": "modify"}]
    data["repo_responsibilities"] = [{"repo": "notification-service", "role": "modify", "responsibility": "create service scaffold, APIs, persistence, CI/CD, deployment and observability baseline"}, {"repo": "monolith", "role": "modify", "responsibility": "add adapter and traffic flag"}, {"repo": "identity-service", "role": "confirm_only", "responsibility": "confirm user validation contract"}]
    data["cross_repo_contracts"] = [{"producer": "notification-service", "consumer": "monolith", "contract": "POST/GET /api/notification/preferences", "compatibility": "new additive provider API behind monolith flag", "failure_mode": "adapter falls back to monolith preference read until cutover"}]
    data["cross_repo_dependency_graph"] = [{"from": "notification-service", "to": "monolith", "contract": "preference API", "change": "provider before consumer flag"}, {"from": "identity-service", "to": "notification-service", "contract": "user validation read API", "change": "confirm only"}]
    data["data_flow"] = [{"source": "monolith adapter", "target": "notification-service", "rule": "tenant/user scoped preference update"}, {"source": "notification-service", "target": "notification database", "rule": "write preference and audit"}]
    data["data_ownership"] = [{"business_object": "notification preference", "owner_repo": "notification-service", "write_authority": "notification-service", "consistency_rule": "preference and audit written in one local transaction"}]
    data["integration_sequence"] = [{"step": 1, "actor": "monolith adapter", "action": "call notification-service preference API", "failure_handling": "flag fallback to monolith until cutover"}, {"step": 2, "actor": "notification-service", "action": "validate user through identity-service and write preference", "failure_handling": "return dependency unavailable without partial write"}]
    data["failure_isolation"] = [{"failure": "notification-service unavailable", "isolation": "monolith adapter flag can route back to legacy path", "user_impact": "temporary legacy behavior"}]
    data["security_and_permission"] = [{"control": "service validates auth token, tenant scope, user ownership, and writes consent audit", "impact": "new service must enforce tenant/user data scope"}]
    data["observability"] = [{"signal": "preference_update_success/error", "owner": "notification team"}, {"signal": "identity_validation_latency", "owner": "notification team"}]
    data["monitoring_alerts"] = [{"signal": "preference API error rate", "owner": "notification team", "trigger": "error rate above SLO for 5 minutes", "action": "disable adapter flag and investigate"}]
    data["deployment_topology"] = [{"repo": "notification-service", "artifact": "container image", "environment": "dev/sit/uat/prod"}, {"repo": "monolith", "artifact": "existing monolith artifact", "environment": "standard"}]
    data["deployment_impact"] = [{"order": "notification-service before monolith flag", "config": "service endpoint, database credentials, traffic flag"}]
    data["deployment_impact_matrix"] = [{"repo": "notification-service", "artifact": "container image", "order": 1, "config_change": "database, identity endpoint, alert routing", "restart_required": "new deployment"}, {"repo": "monolith", "artifact": "monolith package", "order": 2, "config_change": "notification-service endpoint and feature flag", "restart_required": "standard deploy"}]
    data["new_service_design"] = {
        "creation_reason": "Existing monolith account modules cannot safely own multi-channel notification preference lifecycle, consent audit, and multiple downstream consumers without increasing account coupling and release risk.",
        "existing_system_fit_analysis": {"reuse_candidates": ["identity-service user contract", "monolith account UI"], "rejected_existing_owners": ["monolith account module rejected because it would become provider for unrelated sender consumers"], "decision": "create notification-service and keep monolith as compatibility consumer"},
        "responsibility_boundary": "notification-service owns preference APIs, validation, persistence, and consent audit",
        "non_responsibilities": ["user identity ownership", "message delivery provider execution", "historical delivery log migration"],
        "technology_stack": {"language": "Java", "framework": "Spring Boot", "database": "MySQL", "build": "Maven"},
        "repository_bootstrap": {"repo_name": "notification-service", "default_branch": "main", "scaffold": "Spring Boot service with api/domain/repository/config packages", "owned_directories": ["src/main/java/com/example/notification", "src/test/java/com/example/notification"], "initial_files": ["pom.xml", "Dockerfile", "application.yml", "PreferenceController.java"]},
        "module_structure": {"api": "REST controllers and DTOs", "domain": "preference validation and audit orchestration", "repository": "preference and audit persistence", "config": "identity client and database configuration"},
        "api_contracts": {"provider": "notification-service", "consumers": ["monolith", "future sender services"], "contracts": ["POST /api/notification/preferences", "GET /api/notification/preferences/{userId}"]},
        "ci_cd_baseline": {"build": "mvn -q -DskipTests package", "test": "mvn test", "package": "docker build", "deploy": "standard service deployment pipeline", "quality_gates": ["unit tests", "API contract tests", "image build"]},
        "configuration_model": {"environments": ["dev", "sit", "uat", "prod"], "config_sources": ["application.yml", "environment variables", "secret manager"], "secret_handling": "database credentials and tokens in secret manager only", "restart_policy": "configuration changes require service restart unless marked dynamic"},
        "deployment_model": {"artifact": "container image", "runtime": "Kubernetes deployment", "network_entry": "internal service route behind gateway", "dependency_order": "database migration, notification-service deploy, monolith adapter flag", "capacity_baseline": "two replicas and preference API SLO baseline"},
        "observability_baseline": {"logs": "structured API/audit logs without PII payload", "metrics": "request count, error rate, latency, update success", "traces": "trace id across monolith, notification-service, identity-service", "alerts": "API error rate and dependency latency", "dashboards": "notification-service service health dashboard"},
        "security_baseline": {"authn": "validate upstream token", "authz": "customer can mutate own preferences only", "tenant_scope": "tenant_id required on read/write", "audit": "write consent audit for every mutation", "data_protection": "mask user identifiers in logs"},
        "maintenance_ownership": {"owning_team": "notification platform team", "oncall": "notification service oncall rotation", "runbook": "service startup, dependency failure, rollback and flag-disable runbook", "upgrade_policy": "monthly dependency updates and API compatibility review"},
        "rollout_migration": {"strategy": "deploy service dark, enable monolith adapter by tenant flag, then expand", "compatibility_window": "one release cycle with monolith fallback", "cutover": "switch account UI reads/writes to notification-service after contract tests and UAT", "validation": "API contract tests, adapter integration tests, production smoke"},
        "rollback_strategy": {"code": "revert monolith adapter or notification-service deployment", "config": "disable adapter traffic flag", "data": "leave new preference tables dormant and do not destructively roll back", "traffic": "route account UI back to monolith preference path"},
    }
    data["migration_strategy"] = [{"migration_type": "new tables and traffic migration", "forward_action": "create schema, deploy service dark, enable adapter flag by tenant", "backward_compatibility": "monolith legacy path remains available for one release", "rollback_action": "disable adapter flag and keep new data dormant"}]
    data["gray_release_strategy"] = [{"strategy": "tenant allowlist and traffic flag", "fallback": "disable flag to route monolith back to legacy preference path"}]
    data["rollback_strategy"] = [{"repo": "notification-service", "steps": ["disable monolith traffic flag", "roll back service image if needed"], "data_risk": "new preference rows remain dormant"}, {"repo": "monolith", "steps": ["disable adapter flag", "revert adapter if necessary"], "data_risk": "legacy path remains source until cutover"}]
    data["decision_records"] = [{"decision": "create notification-service", "alternatives": ["extend monolith account module"], "reason": "multi-consumer preference lifecycle needs independent ownership and audit controls"}]
    return data


def render(doc_id: str, title: str, out_dir: Path, example: bool = False, new_service_example: bool = False) -> dict[str, Any]:
    if new_service_example:
        technical = new_service_example_technical(doc_id, title)
        architecture = new_service_example_architecture(doc_id, title)
    else:
        technical = example_technical(doc_id, title) if example else empty_technical(doc_id, title)
        architecture = example_architecture(doc_id, title) if example else empty_architecture(doc_id, title)
    write_json(out_dir / "technical_design.json", technical)
    write_json(out_dir / "architecture_design.json", architecture)
    manifest = {
        "schema": "codex-design-template-manifest-v1",
        "doc_id": doc_id,
        "title": title,
        "example": example,
        "new_service_example": new_service_example,
        "files": {
            "technical_design": str((out_dir / "technical_design.json").resolve()),
            "architecture_design": str((out_dir / "architecture_design.json").resolve()),
        },
        "next_action": "fill concrete facts and run design-architecture-reviewer" if not (example or new_service_example) else "run design-architecture-reviewer regression",
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
    parser.add_argument("--new-service-example", action="store_true")
    args = parser.parse_args()
    manifest = render(args.doc_id, args.title, Path(args.out_dir), args.example, args.new_service_example)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
