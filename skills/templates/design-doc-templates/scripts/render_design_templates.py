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
        "logical_data_flow": [{"source": "", "transform": "", "destination": "", "owner": "", "data_security": ""}],
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


SUMMARY_PROCESS_FLOW_DIAGRAM = """```mermaid
flowchart TD
    User["Step 1: open /summary and trigger useSummaryData"]
    App["Step 2: request summary data from provider-service"]
    Provider["Step 3: return header, totals, and items[]"]
    Render["Step 4: render item rows without recalculating values"]
    User --> App --> Provider --> Render
```"""

SUMMARY_SYSTEM_SEQUENCE_DIAGRAM = """```mermaid
sequenceDiagram
    participant User as user browser
    participant App as web-app summary page
    participant Provider as provider-service
    User->>App: open /summary and trigger useSummaryData
    App->>Provider: request summary data from provider-service
    Provider-->>App: return header, totals, and items[]
    App-->>User: render item rows without recalculating values
```"""

SUMMARY_INTEGRATION_SEQUENCE_DIAGRAM = """```mermaid
sequenceDiagram
    participant App as web-app
    participant Provider as provider-service
    App->>Provider: request summary data from provider-service
    Provider-->>App: items[] remains provider-owned
```"""

SERVICE_PROCESS_FLOW_DIAGRAM = """```mermaid
flowchart TD
    Actor["client: save shared rule"]
    Legacy["legacy-app adapter: submit rule change"]
    Service["service-a: validate requester and scope"]
    Audit["audit log recorded"]
    Actor --> Legacy --> Service --> Audit
```"""

SERVICE_SYSTEM_SEQUENCE_DIAGRAM = """```mermaid
sequenceDiagram
    participant Actor as client browser
    participant Legacy as legacy-app adapter
    participant Service as service-a
    participant Auth as auth-service
    participant DB as service-a database
    Actor->>Legacy: save shared rule
    Legacy->>Service: submit rule change
    Service->>Auth: validate requester and scope
    Auth-->>Service: validation result
    Service->>DB: write rule and audit log
    Service-->>Legacy: return saved rule
    Legacy-->>Actor: success
```"""

SERVICE_INTEGRATION_SEQUENCE_DIAGRAM = """```mermaid
sequenceDiagram
    participant Legacy as legacy-app
    participant Service as service-a
    participant Auth as auth-service
    Legacy->>Service: call service-a rule API
    Service->>Auth: validate requester through auth-service and write rule
    Service-->>Legacy: rule response
```"""


def summary_display_architecture_framing(doc_id: str, title: str) -> dict[str, Any]:
    return {
        "schema": "codex-architecture-framing-v1",
        "doc_id": doc_id,
        "title": title,
        "decision": "pass",
        "system_boundary": {
            "decision_type": "modify_existing_system",
            "owner_repo": "web-app",
            "owner_repo_path": "",
            "new_service_decision": {
                "required": False,
                "reason": "The requirement renders an existing provider response field in the UI; ownership and provider contracts stay unchanged.",
                "rejected_existing_owners": [],
                "creation_conditions": [],
            },
        },
        "repo_responsibilities": [
            {"repo": "web-app", "role": "modify", "responsibility": "render item rows from the existing provider response"},
            {"repo": "provider-service", "role": "confirm_only", "responsibility": "confirm items[] remains part of the response contract"},
        ],
        "runtime_entrypoints": [
            {
                "kind": "frontend_action",
                "trigger": "user opens the summary page",
                "actor": "user browser",
                "repo": "web-app",
                "entrypoint": "src/summary/useSummaryData.ts -> src/summary/SummaryPanel.tsx",
                "downstream": ["provider-service GET /api/provider/items?contextId={contextId}"],
            }
        ],
        "dependency_graph": {
            "degree": 1,
            "classification": "one_degree_existing_contract",
            "edges": [
                {
                    "from": "web-app summary page",
                    "to": "provider-service",
                    "interaction": "GET /api/provider/items?contextId={contextId}",
                    "change_type": "reuse_existing_contract",
                    "contract": "provider response items[]",
                }
            ],
        },
        "provider_consumer": [
            {
                "provider": "provider-service",
                "consumer": "web-app",
                "contract": "GET /api/provider/items returns header, totals, and items[]",
                "compatibility": "unchanged provider contract; frontend consumes existing field",
            }
        ],
        "data_ownership": [
            {
                "business_object": "item detail",
                "owner_repo": "provider-service",
                "write_authority": "provider-service",
                "consumer_rule": "web-app displays values read-only and must not recalculate fields",
            }
        ],
        "release_order": [
            {"order": 1, "repo": "provider-service", "action": "confirm contract evidence only"},
            {"order": 2, "repo": "web-app", "action": "deploy summary UI rendering change"},
        ],
        "rollback_boundary": [{"repo": "web-app", "rollback": "revert or hide item row rendering", "data_risk": "none"}],
        "blockers": [],
    }


def shared_service_architecture_framing(doc_id: str, title: str) -> dict[str, Any]:
    return {
        "schema": "codex-architecture-framing-v1",
        "doc_id": doc_id,
        "title": title,
        "decision": "pass",
        "system_boundary": {
            "decision_type": "new_service_required",
            "owner_repo": "service-a",
            "owner_repo_path": "",
            "new_service_decision": {
                "required": True,
                "reason": "A dedicated owner is needed for shared rule lifecycle, audit, and multiple consumers.",
                "rejected_existing_owners": [
                    {"repo": "legacy-app", "reason": "would keep consumers coupled to legacy release cadence and persistence"},
                    {"repo": "auth-service", "reason": "owns authentication only and should not own shared rule lifecycle"},
                ],
                "creation_conditions": ["new CI/CD baseline", "owned database schema", "service SLO and oncall", "provider API contract tests"],
            },
        },
        "repo_responsibilities": [
            {"repo": "service-a", "role": "create", "responsibility": "own rule APIs, validation, persistence, audit, observability, and deployment baseline"},
            {"repo": "legacy-app", "role": "modify", "responsibility": "add compatibility adapter and traffic flag for the legacy path"},
            {"repo": "auth-service", "role": "confirm_only", "responsibility": "confirm requester validation read contract"},
        ],
        "runtime_entrypoints": [
            {
                "kind": "frontend_action",
                "trigger": "client saves a shared rule",
                "actor": "client browser",
                "repo": "legacy-app",
                "entrypoint": "legacy settings page -> adapter",
                "downstream": ["service-a POST /api/service-a/rules", "auth-service validation"],
            },
            {
                "kind": "api_request",
                "trigger": "downstream consumer reads the shared rule before execution",
                "actor": "consumer service",
                "repo": "service-a",
                "entrypoint": "GET /api/service-a/rules/{subjectId}",
                "downstream": ["service-a database"],
            },
        ],
        "dependency_graph": {
            "degree": 2,
            "classification": "multi_degree_new_provider",
            "edges": [
                {"from": "legacy app", "to": "legacy-app adapter", "interaction": "save shared rule", "change_type": "modify_consumer"},
                {"from": "legacy-app adapter", "to": "service-a", "interaction": "POST /api/service-a/rules", "change_type": "new_provider_contract"},
                {"from": "service-a", "to": "auth-service", "interaction": "validate requester and scope", "change_type": "reuse_existing_contract"},
                {"from": "service-a", "to": "service-a database", "interaction": "write rule and audit log", "change_type": "new_data_owner"},
            ],
        },
        "provider_consumer": [
            {"provider": "service-a", "consumer": "legacy-app", "contract": "POST/GET /api/service-a/rules", "compatibility": "new additive provider contract behind adapter flag"},
            {"provider": "auth-service", "consumer": "service-a", "contract": "requester validation read API", "compatibility": "existing contract confirmation only"},
        ],
        "data_ownership": [
            {"business_object": "shared rule", "owner_repo": "service-a", "write_authority": "service-a", "consumer_rule": "legacy-app and consumers read through provider APIs"},
            {"business_object": "requester identity", "owner_repo": "auth-service", "write_authority": "auth-service", "consumer_rule": "service-a validates identity read-only"},
        ],
        "release_order": [
            {"order": 1, "repo": "service-a", "action": "create schema, deploy service dark, verify API and observability baseline"},
            {"order": 2, "repo": "legacy-app", "action": "deploy adapter with traffic flag disabled"},
            {"order": 3, "repo": "legacy-app", "action": "enable tenant allowlist after contract and UAT evidence"},
        ],
        "rollback_boundary": [
            {"repo": "legacy-app", "rollback": "disable adapter flag and route back to the legacy path", "data_risk": "new rows remain dormant"},
            {"repo": "service-a", "rollback": "roll back service image after traffic is disabled", "data_risk": "no destructive data rollback"},
        ],
        "blockers": [],
    }


def example_technical(doc_id: str, title: str) -> dict[str, Any]:
    data = empty_technical(doc_id, title)
    data.update({
        "architecture_framing_ref": "architecture_framing.json",
        "architecture_framing": summary_display_architecture_framing(doc_id, title),
        "design_scope": {"in_scope": ["summary item display"], "out_of_scope": ["source calculation"], "assumptions": ["existing API already returns details"], "non_goals": ["backend aggregation change"]},
        "current_state_analysis": {"existing_behavior": "summary page already renders header and totals from the provider response", "code_entrypoints": ["src/summary/SummaryPanel.tsx", "src/summary/useSummaryData.ts"], "known_constraints": ["provider remains source of truth", "no extra request is introduced"], "reuse_points": ["existing row renderer", "existing response type"]},
        "problem_analysis": {
            "current_behavior": "The summary page already loads provider data and renders overall totals, but it does not expose the returned item breakdown.",
            "business_problem": "Users cannot review item-level details before confirmation, which creates avoidable support questions even though the provider already owns the data.",
            "process_gap": "The frontend has the response available but drops items[] during rendering; no backend aggregation or persistence path needs to change.",
            "code_entrypoints": ["src/summary/SummaryPanel.tsx", "src/summary/useSummaryData.ts"],
            "constraints": ["provider-service remains the source of truth", "no additional summary request", "render missing items as empty state"],
            "design_goals": ["render item label and amount before confirmation", "preserve existing provider API compatibility", "avoid duplicating data logic in web"],
            "success_criteria": ["item rows display when items[] is present", "responses without items render the previous header and totals view", "browser regression and summary test evidence pass"],
        },
        "requirement_trace": [{"requirement_id": "REQ-1", "summary": "show item breakdown on summary page"}],
        "business_rule_mapping": [{"requirement_id": "REQ-1", "technical_enforcement": "web page renders provider item fields", "source_of_truth": "provider API response"}],
        "process_flow": [{"flow_name": "summary review", "actors": ["user"], "steps": [{"step": 1, "actor": "user", "action": "open /summary and trigger useSummaryData", "input": "current data", "output": "item breakdown", "exception": "provider error shows existing fallback"}], "success_end_state": "item breakdown is visible before confirmation", "failure_end_states": ["provider unavailable"]}],
        "process_flow_diagram": SUMMARY_PROCESS_FLOW_DIAGRAM,
        "module_decomposition": [{"module": "src/summary/SummaryPanel.tsx", "responsibility": "render item rows", "input": "provider response", "output": "summary UI", "dependencies": ["provider API"], "cohesion_reason": "presentation-only module", "coupling_control": "no data calculation in UI"}],
        "logical_data_flow": [{"source": "provider API", "transform": "format item rows", "destination": "summary page", "owner": "provider-service", "data_security": "no sensitive personal data"}],
        "target_behavior": [{"requirement_id": "REQ-1", "behavior": "user sees item breakdown before confirmation"}],
        "api_contracts": [{"contract": "GET /api/provider/items returns items[] field unchanged", "compatibility": "additive rendering only", "old_consumer_impact": "none", "source_evidence": "summary_display_architecture_framing.provider_consumer", "frontend_proxy_path": "src/summary/useSummaryData.ts"}],
        "interface_examples": [{"name": "provider response", "request": "GET /api/provider/items?contextId={contextId}", "response": "{\"items\":[{\"label\":\"Item A\",\"amount\":100}]}", "error_response": "{\"error\":\"provider unavailable\"}"}],
        "compatibility_strategy": [{"old_consumer": "summary page", "old_data": "responses without items", "rollback": "hide rows", "behavior": "empty items render nothing"}],
        "compatibility_matrix": [{"consumer": "summary page", "old_behavior": "header and totals only", "new_behavior": "item rows displayed when present", "compatibility": "additive", "rollback_behavior": "item rows hidden"}],
        "data_design": [{"read_rule": "read existing items array", "write_rule": "no write", "migration": "none"}],
        "data_model_design": {"applicable": False, "not_applicable_reason": "The change reads the existing provider response items[] field for display only and does not add, remove, backfill, or persist any entity/table/field."},
        "system_interaction_sequence": {
            "applicable": True,
            "participants": ["user browser", "web-app summary page", "provider-service"],
            "sequence": [
                {"step": 1, "from": "user browser", "to": "web-app summary page", "action": "open /summary and trigger useSummaryData", "success": "summary load starts", "failure": "existing route error is shown", "state_transition": "page open -> loading", "source_evidence": "runtime_entrypoints.frontend_action"},
                {"step": 2, "from": "web-app summary page", "to": "provider-service", "action": "request summary data from provider-service", "success": "provider response is received", "failure": "existing provider error handling runs", "state_transition": "loading -> response received", "source_evidence": "provider_consumer.provider-service"},
                {"step": 3, "from": "provider-service", "to": "web-app summary page", "action": "return header, totals, and items[]", "success": "item fields are available for rendering", "failure": "items missing is treated as empty list", "state_transition": "response received -> summary model ready", "source_evidence": "api_contracts.items[]"},
                {"step": 4, "from": "web-app summary page", "to": "user browser", "action": "render item rows without recalculating values", "success": "user sees item breakdown", "failure": "header and totals remain visible", "state_transition": "summary model ready -> review visible", "source_evidence": "ui_ue_design.summary panel"},
            ],
            "timeout_retry": "Preserve existing useSummaryData timeout and retry behavior; no new retry loop is introduced for item rendering.",
            "idempotency": "Read-only provider query remains idempotent and the UI render has no side effect.",
            "consistency": "Item display uses the same response snapshot as header and totals, so rows cannot drift from displayed totals.",
        },
        "system_sequence_diagram": SUMMARY_SYSTEM_SEQUENCE_DIAGRAM,
        "mq_interactions": [{"applicable": False, "not_applicable_reason": "Summary display only handles the browser load event and does not publish or consume asynchronous MQ messages."}],
        "transaction_consistency": {"applicable": False, "not_applicable_reason": "The selected solution is read-only UI rendering and does not introduce database writes, distributed transactions, or compensating updates."},
        "observability_design": {
            "logs": "Reuse existing frontend error logging for provider load failures; do not log payload values.",
            "metrics": "Reuse summary page error-rate and render-failure counters; no new backend metric is required for a display-only change.",
            "traces": "Keep existing request trace correlation from web-app to provider-service.",
            "alerts": "Existing frontend error alert remains sufficient; rollback if error rate increases after rollout.",
        },
        "permission_model": [{"role": "user", "rule": "own summary only", "negative_case": "cannot view another subject"}],
        "exception_and_edge_cases": [{"case": "items missing", "handling": "show totals only"}],
        "non_functional_requirements": [{"type": "performance", "impact": "no extra request"}, {"type": "security", "impact": "no new sensitive data"}],
        "solution_options": [
            {"option_id": "T1", "name": "render existing API field", "description": "UI-only render", "when_to_choose": ["provider API already returns items", "acceptance only changes summary display"], "implementation_outline": ["read SummaryPanel and useSummaryData", "render item rows from existing response", "preserve existing fallback when items are absent"], "pros": ["small change", "keeps provider source of truth"], "cons": ["depends on existing field", "less reusable if other pages need items"], "risk_level": "low", "risk_controls": ["browser regression", "no data calculation in UI"], "validation": "browser evidence", "test_evidence": ["browser screenshot", "summary regression output"], "performance_impact": "none", "rollout_impact": "web bundle only", "rollback_strategy": "revert UI"},
            {"option_id": "T2", "name": "calculate in web", "description": "derive items in UI", "when_to_choose": ["API cannot expose item breakdown", "temporary display is accepted by data owner"], "implementation_outline": ["read provider inputs", "derive item rows in web", "add unit tests for edge cases"], "pros": ["independent", "fast local change"], "cons": ["duplicates provider logic", "higher correctness risk"], "risk_level": "high", "risk_controls": ["owner review", "unit tests for edge cases"], "validation": "unit tests", "test_evidence": ["unit test output", "browser screenshot"], "performance_impact": "minor CPU", "rollout_impact": "web bundle only but behavior risk increases", "rollback_strategy": "revert UI"},
        ],
        "option_comparison_matrix": [
            {"criterion": "correctness", "weight": 5, "scores": {"T1": 5, "T2": 2}, "winner": "T1", "reason": "provider remains source of truth"},
            {"criterion": "blast_radius", "weight": 5, "scores": {"T1": 5, "T2": 4}, "winner": "T1", "reason": "render-only change"},
            {"criterion": "rollback", "weight": 4, "scores": {"T1": 5, "T2": 5}, "winner": "tie", "reason": "both rollback by reverting web"},
            {"criterion": "test_surface", "weight": 4, "scores": {"T1": 4, "T2": 3}, "winner": "T1", "reason": "less logic to validate"},
        ],
        "option_score_summary": {"T1": 96, "T2": 67, "scoring_rule": "weighted qualitative score"},
        "selected_solution": {"selected_option_id": "T1", "selection_reason": "keeps provider source of truth", "decision_criteria": ["correctness", "low coupling"], "tradeoffs": ["UI depends on existing field"], "rejected_alternative_reasoning": [{"option_id": "T2", "reason": "duplicates data logic in the UI"}]},
        "design_traceability_matrix": [{"requirement_id": "REQ-1", "process_flow_refs": ["summary review"], "module_refs": ["src/summary/SummaryPanel.tsx"], "data_flow_refs": ["provider API->summary page"], "api_contract_refs": ["items[]"], "ui_ue_refs": ["summary panel"], "test_refs": ["UI-1"], "acceptance_refs": ["AC-1"], "selected_option_id": "T1", "decision_reason": "lowest risk"}],
        "acceptance_mapping": [{"acceptance_id": "AC-1", "design_refs": ["summary panel"], "evidence_required": ["browser screenshot"]}],
        "ui_ue_design": [{"page_or_route": "/summary", "user_goal": "confirm item details", "entry_point": "current review page", "layout": "summary panel", "interaction_flow": ["open page"], "states": ["loading", "success", "error"], "field_rules": ["show each item label and amount"], "permission_visibility": "user own data only", "acceptance_evidence": "browser screenshot"}],
        "test_strategy": [{"summary": "browser, regression, and acceptance evidence required", "evidence": ["browser screenshot", "regression evidence"], "test_design_ref": "test_design.json"}],
        "test_design_ref": "test_design.json",
    })
    return data


def example_architecture(doc_id: str, title: str) -> dict[str, Any]:
    data = empty_architecture(doc_id, title)
    data.update({
        "architecture_framing_ref": "architecture_framing.json",
        "architecture_framing": summary_display_architecture_framing(doc_id, title),
        "architecture_scope": {"in_scope": ["web summary page"], "out_of_scope": ["provider service logic"], "assumptions": ["contract exists"], "decision_drivers": ["low coupling"]},
        "current_architecture": {"system_context": "web-app consumes provider-service during summary display and renders returned data", "repo_entrypoints": ["web-app/src/summary/SummaryPanel.tsx", "provider-service existing response endpoint"], "upstream_downstream": ["provider-service -> web-app"], "constraints": ["provider-service remains source of truth"]},
        "architecture_options": [
            {"option_id": "A1", "name": "web only", "description": "render existing contract", "when_to_choose": ["items[] contract already exists", "web-app only changes presentation"], "owner_repos": ["web-app"], "confirm_only_repos": ["provider-service"], "integration_impact": "no new provider-consumer contract", "deployment_impact": "deploy web bundle only", "rollback_complexity": "low", "pros": ["safe", "low coordination"], "cons": ["UI local", "less reusable"], "risk_level": "low", "risk_controls": ["contract confirmation", "browser evidence"], "validation": "browser", "performance_impact": "none", "rollback_strategy": "revert web"},
            {"option_id": "A2", "name": "provider API change", "description": "new endpoint", "when_to_choose": ["contract lacks required item data", "multiple consumers need the same shape"], "owner_repos": ["provider-service", "web-app"], "confirm_only_repos": ["reporting-service"], "integration_impact": "provider-consumer contract and integration tests", "deployment_impact": "provider-service before web-app or compatible rollout", "rollback_complexity": "medium", "pros": ["explicit", "shared"], "cons": ["contract risk", "ordered release"], "risk_level": "medium", "risk_controls": ["contract freeze", "integration evidence"], "validation": "API+UI", "performance_impact": "extra request or payload growth", "rollback_strategy": "revert both"},
        ],
        "architecture_fit_matrix": [
            {"criterion": "ownership_clarity", "weight": 5, "scores": {"A1": 5, "A2": 3}, "winner": "A1", "reason": "web owns rendering"},
            {"criterion": "release_coordination", "weight": 5, "scores": {"A1": 5, "A2": 2}, "winner": "A1", "reason": "web-only deploy"},
            {"criterion": "contract_risk", "weight": 5, "scores": {"A1": 5, "A2": 2}, "winner": "A1", "reason": "contract unchanged"},
            {"criterion": "rollback", "weight": 4, "scores": {"A1": 5, "A2": 3}, "winner": "A1", "reason": "single repo rollback"},
        ],
        "architecture_score_summary": {"A1": 95, "A2": 70, "scoring_rule": "weighted qualitative score"},
        "selected_architecture": {"selected_option_id": "A1", "selection_reason": "no API change", "decision_criteria": ["compatibility", "low coupling"], "tradeoffs": ["UI renders existing data"], "rejected_alternative_reasoning": [{"option_id": "A2", "reason": "adds cross-repo contract and release-order risk"}]},
        "architecture_traceability_matrix": [{"requirement_id": "REQ-1", "component_boundary_refs": ["web-app owns rendering"], "module_topology_refs": ["web-app/summary"], "data_flow_refs": ["provider-service->web-app"], "integration_sequence_refs": ["summary load"], "contract_refs": ["items[]"], "selected_architecture_option_id": "A1", "decision_reason": "lowest integration risk"}],
        "component_boundaries": [{"component": "web-app", "role": "render summary", "exclusion": "does not own provider data generation"}],
        "module_topology": [{"repo": "web-app", "module": "summary", "responsibility": "display", "depends_on": ["provider-service"], "boundary_rule": "read-only API consumer", "change_type": "modify"}],
        "repo_responsibilities": [{"repo": "web-app", "role": "modify", "responsibility": "render item rows"}, {"repo": "provider-service", "role": "confirm_only", "responsibility": "contract unchanged"}],
        "cross_repo_contracts": [{"producer": "provider-service", "consumer": "web-app", "contract": "items[]", "compatibility": "unchanged", "failure_mode": "empty items render none"}],
        "cross_repo_dependency_graph": [{"from": "provider-service", "to": "web-app", "contract": "provider response items[]", "change": "confirm only"}],
        "data_flow": [{"source": "provider-service", "target": "web-app", "rule": "display only"}],
        "data_ownership": [{"business_object": "item detail", "owner_repo": "provider-service", "write_authority": "provider-service", "consistency_rule": "web read only"}],
        "integration_sequence": [{"step": 1, "from": "web-app", "to": "provider-service", "owner_repo": "web-app", "contract": "GET /api/provider/items?contextId={contextId}", "data": "header, totals, items[]", "action": "request summary data from provider-service", "failure_handling": "show existing error"}],
        "integration_sequence_diagram": SUMMARY_INTEGRATION_SEQUENCE_DIAGRAM,
        "failure_isolation": [{"failure": "provider-service unavailable", "isolation": "web-app keeps existing header and totals view", "user_impact": "display fallback only"}],
        "security_and_permission": [{"control": "user can only see own summary", "impact": "no new permission model"}],
        "observability": [{"signal": "provider load error", "owner": "web-app"}],
        "monitoring_alerts": [{"signal": "summary render error rate", "owner": "web-app", "trigger": "error rate increase", "action": "hide new rows"}],
        "deployment_topology": [{"repo": "web-app", "artifact": "frontend bundle", "environment": "browser"}],
        "deployment_impact": [{"order": "web-app only", "config": "no new backend config"}],
        "deployment_impact_matrix": [{"repo": "web-app", "artifact": "frontend bundle", "order": 1, "config_change": "none", "restart_required": "browser refresh"}],
        "new_service_design": {},
        "migration_strategy": [{"migration_type": "none", "forward_action": "render existing field", "backward_compatibility": "current header/totals view remains", "rollback_action": "hide rows"}],
        "gray_release_strategy": [{"strategy": "browser only rollout", "fallback": "hide row rendering"}],
        "rollback_strategy": [{"repo": "web-app", "steps": ["remove row rendering"], "data_risk": "none"}],
        "decision_records": [{"decision": "render existing provider field", "alternatives": ["derive values in web"], "reason": "keep provider source of truth"}],
    })
    return data


def new_service_example_technical(doc_id: str, title: str) -> dict[str, Any]:
    data = example_technical(doc_id, title)
    data["architecture_framing"] = shared_service_architecture_framing(doc_id, title)
    data["design_scope"] = {"in_scope": ["create service-a for shared rule lifecycle"], "out_of_scope": ["replace downstream consumers in first release"], "assumptions": ["auth-service requester contract exists"], "non_goals": ["migrate historical records"]}
    data["current_state_analysis"] = {"existing_behavior": "legacy-app owns the shared rule UI and persistence today, auth-service owns requester identity, and downstream consumers lack an independent rule API", "code_entrypoints": ["legacy-app/rules", "auth-service/users"], "known_constraints": ["legacy compatibility must remain during first release", "auditable changes must be preserved"], "reuse_points": ["auth-service validation", "legacy settings UI"]}
    data["problem_analysis"] = {
        "current_behavior": "The existing legacy path updates rule state inline and downstream consumers read from indirect paths, which makes ownership and audit hard to reason about.",
        "business_problem": "Multiple consumers need rule data, and keeping it inside the legacy app would make release coordination and audit brittle.",
        "process_gap": "There is no dedicated provider API for rule lifecycle, and the legacy adapter would have to own both consumer compatibility and provider write semantics.",
        "code_entrypoints": ["legacy-app/rules", "auth-service/users"],
        "constraints": ["auth-service remains source of truth for identity", "service-a owns only rules and audit", "first release must support compatible read path from legacy-app"],
        "design_goals": ["bootstrap service-a", "expose rule read/write APIs", "keep legacy-app as compatibility consumer during migration"],
        "success_criteria": ["rule writes are owned by service-a", "legacy-app can route through adapter without breaking current flow", "service CI, contract tests, and adapter integration pass"],
    }
    data["requirement_trace"] = [{"requirement_id": "REQ-NEW-SVC", "summary": "create service-a for shared rules"}]
    data["business_rule_mapping"] = [{"requirement_id": "REQ-NEW-SVC", "technical_enforcement": "service-a owns rule write APIs and audit log", "source_of_truth": "service-a rule store"}]
    data["process_flow"] = [{"flow_name": "rule update", "actors": ["client", "legacy-app", "service-a"], "steps": [{"step": 1, "actor": "client", "action": "save shared rule", "input": "rule input", "output": "updated rule", "exception": "invalid rule returns validation error"}], "success_end_state": "rule and audit record are persisted", "failure_end_states": ["identity lookup failed", "validation failed"]}]
    data["process_flow_diagram"] = SERVICE_PROCESS_FLOW_DIAGRAM
    data["module_decomposition"] = [
        {"module": "service-a/src/main/java/com/example/servicea/api/RuleController.java", "responsibility": "own rule REST API", "input": "rule request DTO", "output": "rule response DTO", "dependencies": ["RuleService", "auth-service client"], "cohesion_reason": "API layer only maps HTTP contract", "coupling_control": "business rules stay in service/domain layer"},
        {"module": "service-a/src/main/java/com/example/servicea/domain/RuleService.java", "responsibility": "validate rule input and write audit trail", "input": "subject id and rule data", "output": "stored rule", "dependencies": ["RuleRepository", "AuditRepository"], "cohesion_reason": "single owner for rule lifecycle", "coupling_control": "auth-service is read-only dependency"},
    ]
    data["logical_data_flow"] = [{"source": "legacy-app adapter", "transform": "validate requester and rule data", "destination": "service-a rule store", "owner": "service-a", "data_security": "tenant/subject scope and audit required"}]
    data["target_behavior"] = [{"requirement_id": "REQ-NEW-SVC", "behavior": "clients and legacy compatibility adapter use service-a APIs for rule reads and writes"}]
    data["api_contracts"] = [
        {"endpoint": "POST /api/service-a/rules", "request": "RuleUpdateRequest", "response": "RuleResponse", "compatibility": "new additive provider API", "old_consumer_impact": "legacy-app migrates through adapter without UI contract break", "source_evidence": "shared_service_architecture_framing.provider_consumer", "controller_file": "service-a/src/main/java/.../RuleController.java"},
        {"endpoint": "GET /api/service-a/rules/{subjectId}", "request": "subjectId path parameter", "response": "RuleResponse", "compatibility": "new read API for downstream consumers", "old_consumer_impact": "none for first release", "source_evidence": "shared_service_architecture_framing.provider_consumer", "controller_file": "service-a/src/main/java/.../RuleController.java"},
    ]
    data["compatibility_strategy"] = [{"old_consumer": "legacy-app settings", "old_data": "local rule read/write", "rollback": "disable adapter flag", "behavior": "legacy path remains available"}]
    data["compatibility_matrix"] = [{"consumer": "legacy-app settings", "old_behavior": "local rule read/write", "new_behavior": "adapter calls service-a", "compatibility": "flag controlled", "rollback_behavior": "disable adapter flag"}]
    data["data_design"] = [{"read_rule": "read existing rule records", "write_rule": "write rule and audit in one transaction", "migration": "new rule tables"}]
    data["data_model_design"] = {
        "applicable": True,
        "entities": [{"name": "shared_rule", "owner": "service-a"}, {"name": "rule_audit", "owner": "service-a"}],
        "table_schema_changes": [
            {"table": "shared_rule", "field": "subject_id", "type": "varchar", "nullable": False, "default": "none", "index": "unique tenant_id + subject_id", "migration": "create nullable-safe table before traffic", "rollback": "keep dormant table after traffic rollback"},
            {"table": "rule_audit", "field": "request_id", "type": "varchar", "nullable": False, "default": "none", "index": "unique request_id", "migration": "create audit table before traffic", "rollback": "keep audit rows for traceability"},
        ],
        "field_rules": [
            {"field": "tenant_id", "rule": "required on every read/write and included in unique keys"},
            {"field": "request_id", "rule": "required for idempotent writes and audit deduplication"},
            {"field": "status", "rule": "current rule row must move only through valid lifecycle states"},
        ],
        "read_write_rules": [
            {"operation": "read", "rule": "service-a reads shared_rule by tenant_id and subject_id only"},
            {"operation": "write", "rule": "service-a writes shared_rule and rule_audit in one local transaction"},
        ],
        "migration_strategy": "create new tables before enabling the adapter flag; no destructive backfill in first release",
        "rollback_strategy": "disable adapter traffic and keep new tables dormant; do not delete audit evidence",
        "key_invariants": ["rule updates must record audit", "each subject has one current rule row"],
        "ownership": "service-a owns rule and audit; auth-service owns identity",
    }
    data["table_schema_changes"] = data["data_model_design"]["table_schema_changes"]
    data["cache_strategy"] = {
        "applicable": True,
        "decision": "no_cache",
        "reason": "rule reads/writes require tenant-scoped correctness and immediate consistency during migration",
        "key_design": "",
        "ttl": "",
        "invalidation": "",
        "consistency_risk": "stale rule reads could apply obsolete behavior",
        "evidence_required": ["integration test proves read-after-write without cache"],
    }
    data["system_interaction_sequence"] = {
        "applicable": True,
        "participants": ["legacy-app adapter", "service-a", "auth-service", "service-a database"],
        "sequence": [
            {"step": 1, "from": "legacy-app adapter", "to": "service-a", "action": "submit rule change", "success": "provider accepts request", "failure": "legacy validation error shown", "state_transition": "form editing -> submit pending", "source_evidence": "runtime_entrypoints.frontend_action"},
            {"step": 2, "from": "service-a", "to": "auth-service", "action": "validate requester and scope", "success": "requester ownership is confirmed", "failure": "dependency unavailable and no write occurs", "state_transition": "submit pending -> validation pending", "source_evidence": "provider_consumer.auth-service"},
            {"step": 3, "from": "service-a", "to": "service-a database", "action": "write rule and audit log", "success": "rule and audit commit in one transaction", "failure": "transaction rolls back", "state_transition": "validation pending -> rule persisted", "source_evidence": "data_model_design.read_write_rules"},
            {"step": 4, "from": "service-a", "to": "legacy-app adapter", "action": "return saved rule", "success": "adapter can show success state", "failure": "adapter surfaces existing dependency error", "state_transition": "rule persisted -> response returned", "source_evidence": "compatibility_strategy.flag controlled"},
        ],
        "timeout_retry": "Adapter retries should remain bounded and should not duplicate rule writes.",
        "idempotency": "request_id per rule update prevents duplicate audit writes.",
        "consistency": "rule and audit are committed in one service-a transaction",
    }
    data["system_sequence_diagram"] = SERVICE_SYSTEM_SEQUENCE_DIAGRAM
    data["mq_interactions"] = [{"applicable": False, "not_applicable_reason": "Rule update path is synchronous and does not publish MQ messages in the first release."}]
    data["transaction_consistency"] = {"applicable": True, "boundary": "service-a writes rule and audit record in one local transaction", "idempotency": "request_id per update", "compensation": "manual replay from audit request log if downstream adapter times out after commit", "rollback": "disable adapter traffic and keep committed rules as dormant data"}
    data["observability_design"] = {"logs": "Write structured API, validation, and audit logs without raw payloads.", "metrics": "Track update success rate, validation failure rate, and adapter fallback count.", "traces": "Propagate trace id across legacy-app, adapter, auth-service, and service-a.", "alerts": "Alert on API errors, validation failures, and adapter fallback spikes."}
    data["permission_model"] = [{"role": "client", "rule": "own rules only", "negative_case": "cannot update another subject's rule"}]
    data["exception_and_edge_cases"] = [{"case": "identity lookup fails", "handling": "reject write without partial update"}, {"case": "validation fails", "handling": "return field error"}]
    data["non_functional_requirements"] = [{"type": "performance", "impact": "one additional service hop"}, {"type": "security", "impact": "tenant scoping and audit required"}]
    data["solution_options"] = [
        {"option_id": "T1", "name": "new service-a owns rules", "description": "bootstrap a dedicated service for rule lifecycle and audit", "when_to_choose": ["multiple consumers need rule APIs", "legacy ownership would increase coupling"], "implementation_outline": ["create service scaffold", "add rule APIs", "add legacy adapter", "deploy behind traffic flag"], "pros": ["clear ownership", "independent release path"], "cons": ["new operational surface", "requires bootstrap and oncall"], "risk_level": "medium", "risk_controls": ["contract tests", "traffic flag", "runbook"], "validation": "API contract, integration, and deployment smoke tests", "test_evidence": ["API tests", "adapter integration", "CI/CD proof"], "performance_impact": "one new service hop for migrated reads/writes", "rollout_impact": "new deployable plus adapter", "rollback_strategy": "disable adapter flag and route to legacy-app"},
        {"option_id": "T2", "name": "keep rules in legacy-app", "description": "extend existing app module", "when_to_choose": ["single consumer remains", "no independent audit owner needed"], "implementation_outline": ["add legacy fields", "extend existing APIs"], "pros": ["fastest first change", "no new deployable"], "cons": ["keeps consumers coupled to legacy module", "harder audit ownership"], "risk_level": "medium", "risk_controls": ["module boundaries", "regression tests"], "validation": "legacy tests", "test_evidence": ["API tests"], "performance_impact": "no new hop", "rollout_impact": "legacy deploy only", "rollback_strategy": "revert legacy module"},
    ]
    data["option_comparison_matrix"] = [
        {"criterion": "ownership_clarity", "weight": 5, "scores": {"T1": 5, "T2": 2}, "winner": "T1", "reason": "dedicated lifecycle and audit owner"},
        {"criterion": "consumer_scalability", "weight": 5, "scores": {"T1": 5, "T2": 2}, "winner": "T1", "reason": "consumers can consume stable rule APIs"},
        {"criterion": "operational_cost", "weight": 4, "scores": {"T1": 3, "T2": 5}, "winner": "T2", "reason": "new service has bootstrap cost"},
        {"criterion": "rollback_safety", "weight": 4, "scores": {"T1": 4, "T2": 4}, "winner": "tie", "reason": "both can be flag or code reverted"},
    ]
    data["option_score_summary"] = {"T1": 88, "T2": 68, "scoring_rule": "weighted new-service fit score"}
    data["selected_solution"] = {"selected_option_id": "T1", "selection_reason": "The requirement creates an independent rule lifecycle and multiple consumers, so new service ownership is justified despite bootstrap cost.", "decision_criteria": ["ownership clarity", "consumer scalability", "auditability"], "tradeoffs": ["adds operational surface and CI/CD setup"], "rejected_alternative_reasoning": [{"option_id": "T2", "reason": "legacy extension does not provide independent rule ownership for downstream consumers"}]}
    data["design_traceability_matrix"] = [{"requirement_id": "REQ-NEW-SVC", "process_flow_refs": ["rule update"], "module_refs": ["RuleController", "RuleService"], "data_flow_refs": ["legacy-app adapter->service-a"], "api_contract_refs": ["POST /api/service-a/rules"], "ui_ue_refs": ["legacy settings"], "test_refs": ["API-1", "INT-1"], "acceptance_refs": ["AC-NEW-SVC-1"], "selected_option_id": "T1", "decision_reason": "best ownership and consumer scalability"}]
    data["acceptance_mapping"] = [{"acceptance_id": "AC-NEW-SVC-1", "design_refs": ["service-a APIs", "adapter"], "evidence_required": ["service CI", "API contract tests", "adapter integration tests"]}]
    data["ui_ue_design"] = [{"page_or_route": "/settings/rules", "user_goal": "save shared rules", "entry_point": "legacy settings tab", "layout": "existing settings form", "interaction_flow": ["toggle rule", "save", "show success"], "states": ["loading", "success", "validation error", "dependency error"], "field_rules": ["enum only", "tenant scoped subject id"], "permission_visibility": "own account only", "acceptance_evidence": "browser or API integration evidence"}]
    data["test_strategy"] = [{"summary": "service API, adapter integration, CI/CD, and rollback flag evidence required", "evidence": ["mvn test", "contract test", "adapter integration"], "test_design_ref": "test_design.json"}]
    return data


def new_service_example_architecture(doc_id: str, title: str) -> dict[str, Any]:
    data = example_architecture(doc_id, title)
    data["architecture_framing"] = shared_service_architecture_framing(doc_id, title)
    data["architecture_scope"] = {"in_scope": ["new service-a", "legacy compatibility adapter"], "out_of_scope": ["replace downstream consumers in first release"], "assumptions": ["auth-service requester contract exists"], "decision_drivers": ["clear ownership", "auditability", "controlled migration"]}
    data["current_architecture"] = {"system_context": "legacy-app owns the rule UI and persistence today, auth-service owns requester identity, and consumers lack independent rule APIs", "repo_entrypoints": ["legacy-app/rules", "auth-service/users"], "upstream_downstream": ["legacy-app -> service-a", "auth-service -> service-a"], "constraints": ["legacy compatibility must remain during first release"]}
    data["architecture_options"] = [
        {"option_id": "A1", "name": "create service-a", "description": "new service owns rule lifecycle and audit", "when_to_choose": ["multiple consumers need rule APIs", "audit ownership must be isolated"], "owner_repos": ["service-a", "legacy-app"], "confirm_only_repos": ["auth-service"], "integration_impact": "new provider API plus legacy adapter", "deployment_impact": "deploy service-a before enabling adapter flag", "rollback_complexity": "medium", "pros": ["clear ownership", "independent scaling"], "cons": ["new operations baseline", "new service hop"], "risk_level": "medium", "risk_controls": ["traffic flag", "contract tests", "runbook"], "validation": "service smoke, contract, and adapter integration", "performance_impact": "one new API hop", "rollback_strategy": "disable adapter flag"},
        {"option_id": "A2", "name": "keep rules in legacy-app", "description": "extend existing legacy module", "when_to_choose": ["single consumer remains", "no independent audit owner needed"], "owner_repos": ["legacy-app"], "confirm_only_repos": ["auth-service"], "integration_impact": "no new provider", "deployment_impact": "legacy deploy only", "rollback_complexity": "low", "pros": ["lower bootstrap cost", "fewer deployables"], "cons": ["continued coupling", "weaker ownership"], "risk_level": "medium", "risk_controls": ["module boundary review", "regression"], "validation": "legacy tests", "performance_impact": "no new hop", "rollback_strategy": "revert legacy-app"},
    ]
    data["architecture_fit_matrix"] = [
        {"criterion": "ownership_clarity", "weight": 5, "scores": {"A1": 5, "A2": 2}, "winner": "A1", "reason": "new service owns rule lifecycle"},
        {"criterion": "consumer_scalability", "weight": 5, "scores": {"A1": 5, "A2": 2}, "winner": "A1", "reason": "provider API supports multiple consumers"},
        {"criterion": "bootstrap_cost", "weight": 4, "scores": {"A1": 3, "A2": 5}, "winner": "A2", "reason": "legacy has lower initial cost"},
        {"criterion": "rollback", "weight": 4, "scores": {"A1": 4, "A2": 4}, "winner": "tie", "reason": "both have clear rollback"},
    ]
    data["architecture_score_summary"] = {"A1": 88, "A2": 68, "scoring_rule": "weighted architecture fit score"}
    data["selected_architecture"] = {"selected_option_id": "A1", "selection_reason": "New service is selected because rule ownership, auditability, and multiple consumers outweigh bootstrap cost.", "decision_criteria": ["ownership", "consumer scalability", "auditability"], "tradeoffs": ["adds CI/CD and operational baseline"], "rejected_alternative_reasoning": [{"option_id": "A2", "reason": "legacy ownership does not scale to downstream consumers"}]}
    data["architecture_traceability_matrix"] = [{"requirement_id": "REQ-NEW-SVC", "component_boundary_refs": ["service-a owns rules"], "module_topology_refs": ["service-a/api", "service-a/domain", "legacy-app adapter"], "data_flow_refs": ["legacy-app->service-a"], "integration_sequence_refs": ["rule update"], "contract_refs": ["POST /api/service-a/rules"], "selected_architecture_option_id": "A1", "decision_reason": "clear service ownership"}]
    data["component_boundaries"] = [{"component": "service-a", "role": "own rule lifecycle and audit", "exclusion": "does not own identity or external execution"}, {"component": "legacy-app", "role": "compatibility adapter and settings UI", "exclusion": "does not remain long-term source of truth"}]
    data["module_topology"] = [{"repo": "service-a", "module": "api/domain/repository/config", "responsibility": "rule APIs, validation, persistence, audit, configuration", "depends_on": ["auth-service", "service-a database"], "boundary_rule": "identity read-only, rule writes local", "change_type": "create"}, {"repo": "legacy-app", "module": "rule adapter", "responsibility": "route app calls to service-a under flag", "depends_on": ["service-a"], "boundary_rule": "compatibility adapter only", "change_type": "modify"}]
    data["repo_responsibilities"] = [{"repo": "service-a", "role": "modify", "responsibility": "create service scaffold, APIs, persistence, CI/CD, deployment and observability baseline"}, {"repo": "legacy-app", "role": "modify", "responsibility": "add adapter and traffic flag"}, {"repo": "auth-service", "role": "confirm_only", "responsibility": "confirm requester validation contract"}]
    data["cross_repo_contracts"] = [{"producer": "service-a", "consumer": "legacy-app", "contract": "POST/GET /api/service-a/rules", "compatibility": "new additive provider API behind legacy flag", "failure_mode": "adapter falls back to legacy rule read until cutover"}]
    data["cross_repo_dependency_graph"] = [{"from": "service-a", "to": "legacy-app", "contract": "rule API", "change": "provider before consumer flag"}, {"from": "auth-service", "to": "service-a", "contract": "requester validation read API", "change": "confirm only"}]
    data["data_flow"] = [{"source": "legacy-app adapter", "target": "service-a", "rule": "tenant/subject scoped rule update"}, {"source": "service-a", "target": "service-a database", "rule": "write rule and audit"}]
    data["data_ownership"] = [{"business_object": "shared rule", "owner_repo": "service-a", "write_authority": "service-a", "consistency_rule": "rule and audit written in one local transaction"}]
    data["integration_sequence"] = [
        {"step": 1, "from": "legacy-app adapter", "to": "service-a", "owner_repo": "legacy-app", "contract": "POST/GET /api/service-a/rules", "data": "tenant/subject scoped rule request", "action": "call service-a rule API", "failure_handling": "flag fallback to legacy path until cutover"},
        {"step": 2, "from": "service-a", "to": "auth-service", "owner_repo": "service-a", "contract": "auth-service requester validation API", "data": "tenant_id and subject_id validation request plus rule write", "action": "validate requester through auth-service and write rule", "failure_handling": "return dependency unavailable without partial write"},
    ]
    data["integration_sequence_diagram"] = SERVICE_INTEGRATION_SEQUENCE_DIAGRAM
    data["failure_isolation"] = [{"failure": "service-a unavailable", "isolation": "legacy adapter flag can route back to legacy path", "user_impact": "temporary legacy behavior"}]
    data["security_and_permission"] = [{"control": "service validates auth token, tenant scope, subject ownership, and writes audit log", "impact": "new service must enforce tenant/subject data scope"}]
    data["observability"] = [{"signal": "rule_update_success/error", "owner": "service-a team"}, {"signal": "auth_validation_latency", "owner": "service-a team"}]
    data["monitoring_alerts"] = [{"signal": "rule API error rate", "owner": "service-a team", "trigger": "error rate above SLO for 5 minutes", "action": "disable adapter flag and investigate"}]
    data["deployment_topology"] = [{"repo": "service-a", "artifact": "container image", "environment": "dev/sit/uat/prod"}, {"repo": "legacy-app", "artifact": "existing legacy artifact", "environment": "standard"}]
    data["deployment_impact"] = [{"order": "service-a before legacy flag", "config": "service endpoint, database credentials, traffic flag"}]
    data["deployment_impact_matrix"] = [{"repo": "service-a", "artifact": "container image", "order": 1, "config_change": "database, auth endpoint, alert routing", "restart_required": "new deployment"}, {"repo": "legacy-app", "artifact": "legacy package", "order": 2, "config_change": "service-a endpoint and feature flag", "restart_required": "standard deploy"}]
    data["new_service_design"] = {
        "creation_reason": "The legacy app cannot safely own shared rule lifecycle, audit, and multiple downstream consumers without increasing coupling and release risk.",
        "existing_system_fit_analysis": {"reuse_candidates": ["auth-service requester contract", "legacy settings UI"], "rejected_existing_owners": ["legacy module rejected because it would become provider for unrelated consumers"], "decision": "create service-a and keep legacy-app as compatibility consumer"},
        "responsibility_boundary": "service-a owns rule APIs, validation, persistence, and audit",
        "non_responsibilities": ["identity ownership", "external execution ownership", "historical migration ownership"],
        "technology_stack": {"language": "Java", "framework": "Spring Boot", "database": "MySQL", "build": "Maven"},
        "repository_bootstrap": {"repo_name": "service-a", "default_branch": "main", "scaffold": "Spring Boot service with api/domain/repository/config packages", "owned_directories": ["src/main/java/com/example/servicea", "src/test/java/com/example/servicea"], "initial_files": ["pom.xml", "Dockerfile", "application.yml", "RuleController.java"]},
        "module_structure": {"api": "REST controllers and DTOs", "domain": "rule validation and audit orchestration", "repository": "rule and audit persistence", "config": "auth client and database configuration"},
        "api_contracts": {"provider": "service-a", "consumers": ["legacy-app", "future consumer services"], "contracts": ["POST /api/service-a/rules", "GET /api/service-a/rules/{subjectId}"]},
        "ci_cd_baseline": {"build": "mvn -q -DskipTests package", "test": "mvn test", "package": "docker build", "deploy": "standard service deployment pipeline", "quality_gates": ["unit tests", "API contract tests", "image build"]},
        "configuration_model": {"environments": ["dev", "sit", "uat", "prod"], "config_sources": ["application.yml", "environment variables", "secret manager"], "secret_handling": "database credentials and tokens in secret manager only", "restart_policy": "configuration changes require service restart unless marked dynamic"},
        "deployment_model": {"artifact": "container image", "runtime": "Kubernetes deployment", "network_entry": "internal service route behind gateway", "dependency_order": "database migration, service-a deploy, legacy adapter flag", "capacity_baseline": "two replicas and rule API SLO baseline"},
        "observability_baseline": {"logs": "structured API/audit logs without raw payloads", "metrics": "request count, error rate, latency, update success", "traces": "trace id across legacy-app, service-a, auth-service", "alerts": "API error rate and dependency latency", "dashboards": "service-a health dashboard"},
        "security_baseline": {"authn": "validate upstream token", "authz": "client can mutate own rules only", "tenant_scope": "tenant_id required on read/write", "audit": "write audit log for every mutation", "data_protection": "mask identifiers in logs"},
        "maintenance_ownership": {"owning_team": "service-a team", "oncall": "service-a oncall rotation", "runbook": "service startup, dependency failure, rollback and flag-disable runbook", "upgrade_policy": "monthly dependency updates and API compatibility review"},
        "rollout_migration": {"strategy": "deploy service dark, enable legacy adapter by tenant flag, then expand", "compatibility_window": "one release cycle with legacy fallback", "cutover": "switch reads/writes to service-a after contract tests and UAT", "validation": "API contract tests, adapter integration tests, production smoke"},
        "rollback_strategy": {"code": "revert legacy adapter or service-a deployment", "config": "disable adapter traffic flag", "data": "leave new rule tables dormant and do not destructively roll back", "traffic": "route legacy app back to legacy rule path"},
    }
    data["migration_strategy"] = [{"migration_type": "new tables and traffic migration", "forward_action": "create schema, deploy service dark, enable adapter flag by tenant", "backward_compatibility": "legacy path remains available for one release", "rollback_action": "disable adapter flag and keep new data dormant"}]
    data["gray_release_strategy"] = [{"strategy": "tenant allowlist and traffic flag", "fallback": "disable flag to route legacy app back to legacy rule path"}]
    data["rollback_strategy"] = [{"repo": "service-a", "steps": ["disable legacy traffic flag", "roll back service image if needed"], "data_risk": "new rule rows remain dormant"}, {"repo": "legacy-app", "steps": ["disable adapter flag", "revert adapter if necessary"], "data_risk": "legacy path remains source until cutover"}]
    data["decision_records"] = [{"decision": "create service-a", "alternatives": ["extend legacy-app"], "reason": "multi-consumer rule lifecycle needs independent ownership and audit controls"}]
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
