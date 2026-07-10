#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PLACEHOLDERS = ("confirm later", "unknown", "tbd", "todo", "待确认", "后续确认")
PLACEHOLDER_SAFE_KEYS = {"role", "source_evidence", "read_first", "evidence_refs"}
GENERIC_PHRASES = (
    "target module to be confirmed",
    "existing producer",
    "existing contract unless",
    "no api impact confirmed yet",
    "preserve existing contract unless",
    "affected object",
    "target owner",
    "existing entrypoint to be confirmed",
)
TEMPLATE_DECISION_PHRASES = (
    "default to smallest safe change",
    "default to smallest owner-boundary change",
    "lowest initial risk",
    "single owner rollback is simpler",
    "preserving existing contracts is safer by default",
    "higher coordination, contract, and rollback cost",
)
TEMPLATE_OPTION_NAMES = {
    "minimal scoped change",
    "new abstraction or contract",
    "single owner repository change",
    "cross-repository contract change",
}
GENERIC_ENTRYPOINT_NAMES = {
    "application.java",
    "main.java",
    "index.js",
    "index.ts",
    "index.tsx",
    "index.jsx",
    "package.json",
    "package-lock.json",
    "vue.config.js",
    "babel.config.js",
    "readme.md",
    "docker-compose.yml",
}
GENERIC_ENTRYPOINT_PARTS = {"assets", "icons", "plugins", "config", "node_modules"}
REVIEW_AREAS = [
    "requirement_coverage",
    "standalone_readability_review",
    "technical_design_quality",
    "design_depth_review",
    "api_contract_review",
    "data_model_review",
    "permission_model_review",
    "frontend_behavior_review",
    "compatibility_review",
    "performance_review",
    "security_review",
    "cohesion_coupling_review",
    "architecture_boundary_review",
    "architecture_depth_review",
    "repo_responsibility_review",
    "cross_repo_contract_review",
    "deployment_rollback_review",
    "observability_review",
    "testability_review",
    "overengineering_risks",
    "underdesign_risks",
]


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def text_of(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).lower()


def has_placeholder(value: Any, key: str = "") -> bool:
    if key in PLACEHOLDER_SAFE_KEYS:
        return False
    if isinstance(value, dict):
        return any(has_placeholder(item, str(child_key)) for child_key, item in value.items())
    if isinstance(value, list):
        return any(has_placeholder(item, key) for item in value)
    if isinstance(value, str):
        low = value.lower()
        return any(item in low for item in PLACEHOLDERS)
    return False


def has_generic_phrase(value: Any) -> bool:
    blob = text_of(value)
    return any(phrase in blob for phrase in GENERIC_PHRASES)


def looks_like_path(value: str) -> bool:
    path = value.strip()
    return "/" in path or "." in Path(path).name


def is_generic_entrypoint(value: str) -> bool:
    path = value.strip().lower()
    if not path:
        return False
    parts = set(Path(path).parts)
    return Path(path).name in GENERIC_ENTRYPOINT_NAMES or bool(parts & GENERIC_ENTRYPOINT_PARTS)


def executable_command_hint(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    if looks_like_path(stripped) and not any(stripped.startswith(prefix) for prefix in ("npm ", "pnpm ", "yarn ", "pytest", "python", "mvn ", "gradle", "go test", "cargo ", "make ")):
        return False
    return bool(stripped.split())


def missing_required(item: dict[str, Any], keys: list[str]) -> list[str]:
    return [key for key in keys if key not in item or item.get(key) in (None, "", [])]


def meaningful_text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, ensure_ascii=False)


def lacks_detail(value: Any, min_chars: int = 12) -> bool:
    return len(meaningful_text(value)) < min_chars


def is_applicable(value: Any) -> bool:
    return isinstance(value, dict) and value.get("applicable") is True


def has_signal(blob: str, terms: tuple[str, ...]) -> bool:
    return any(term in blob for term in terms)


def finding(area: str, severity: str, message: str, evidence: Any, suggestion: str) -> dict[str, Any]:
    return {"area": area, "severity": severity, "message": message, "evidence": evidence, "suggestion": suggestion}


def highest_scored_option(score_summary: dict[str, Any]) -> str:
    numeric = {str(key): value for key, value in score_summary.items() if key != "scoring_rule" and isinstance(value, int | float)}
    return max(numeric, key=numeric.get) if numeric else ""


def score_findings(findings: list[dict[str, Any]]) -> dict[str, Any]:
    weights = {"blocker": 30, "high": 12, "medium": 5, "low": 2}
    counts = {"blocker": 0, "high": 0, "medium": 0, "low": 0}
    penalty = 0
    for item in findings:
        severity = str(item.get("severity", "")).lower()
        if severity in counts:
            counts[severity] += 1
            penalty += weights[severity]
    score = max(0, 100 - penalty)
    if counts["blocker"] or score < 60:
        level = "block"
    elif counts["high"] or score < 80:
        level = "needs_revision"
    elif counts["medium"] or score < 90:
        level = "reviewable"
    else:
        level = "expert_ready"
    return {"score": score, "level": level, "severity_counts": counts, "minimum_pass_score": 85, "expert_ready_score": 90}


def review_requirements_understanding_gate(technical: dict[str, Any], architecture: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    tech_gate = technical.get("requirements_understanding_gate") if isinstance(technical.get("requirements_understanding_gate"), dict) else {}
    arch_gate = architecture.get("requirements_understanding_gate") if isinstance(architecture.get("requirements_understanding_gate"), dict) else {}
    gate = tech_gate or arch_gate
    if not gate:
        return
    design_allowed = gate.get("design_allowed")
    if design_allowed is False:
        findings.append(finding(
            "requirement_coverage",
            "blocker",
            "requirement understanding gate blocks design",
            {"technical_gate": tech_gate, "architecture_gate": arch_gate},
            "Clarify business intent, business flow, entrypoints, trigger conditions, and acceptance criteria before treating the design as implementation-ready.",
        ))
    required = {
        "business_intent": "State the real business purpose and expected business outcome.",
        "business_flow": "Describe the concrete business flow before technical options.",
        "entrypoints": "Name concrete entrypoints such as frontend action, API, scheduled task, consumer, or manual task.",
    }
    for key, suggestion in required.items():
        value = gate.get(key)
        if (isinstance(value, list) and not value) or (not isinstance(value, list) and lacks_detail(value, 8)):
            findings.append(finding(
                "requirement_coverage",
                "high",
                f"requirement understanding gate lacks {key}",
                gate,
                suggestion,
            ))
    if gate.get("implementation_allowed") is False:
        findings.append(finding(
            "requirement_coverage",
            "blocker" if design_allowed is False else "high",
            "requirement understanding gate does not allow implementation",
            gate,
            "Resolve requirement blockers or explicitly record approved business assumptions before implementation planning.",
        ))


def review_process_flow(process_flow: list[Any], findings: list[dict[str, Any]]) -> None:
    if not process_flow:
        findings.append(finding("technical_design_quality", "high", "process flow is missing", "process_flow empty", "Describe actors, ordered steps, success end state, and failure states."))
        return
    for idx, item in enumerate(process_flow):
        if not isinstance(item, dict):
            findings.append(finding("technical_design_quality", "high", "process flow row must be an object", {"index": idx}, "Use structured flow rows."))
            continue
        missing = missing_required(item, ["flow_name", "actors", "steps", "success_end_state", "failure_end_states"])
        if missing:
            findings.append(finding("technical_design_quality", "high", "process flow lacks required fields", {"index": idx, "missing": missing}, "Add flow_name, actors, steps, success_end_state, and failure_end_states."))
        for step_idx, step in enumerate(as_list(item.get("steps"))):
            if isinstance(step, dict):
                step_missing = missing_required(step, ["step", "actor", "action", "input", "output", "exception"])
                if step_missing:
                    findings.append(finding("technical_design_quality", "high", "process flow step lacks required fields", {"flow_index": idx, "step_index": step_idx, "missing": step_missing}, "Each step needs actor/action/input/output/exception."))


def review_module_decomposition(modules: list[Any], findings: list[dict[str, Any]]) -> None:
    if not modules:
        findings.append(finding("cohesion_coupling_review", "high", "module decomposition is missing", "module_decomposition empty", "Define modules, responsibilities, inputs, outputs, dependencies, cohesion, and coupling control."))
        return
    for idx, item in enumerate(modules):
        if isinstance(item, dict):
            missing = missing_required(item, ["module", "responsibility", "input", "output", "dependencies", "cohesion_reason", "coupling_control"])
            if missing:
                findings.append(finding("cohesion_coupling_review", "high", "module decomposition lacks cohesion/coupling fields", {"index": idx, "missing": missing}, "Add responsibility, IO, dependencies, cohesion_reason, and coupling_control."))


def review_options(options: list[Any], selected: dict[str, Any], area: str, label: str, findings: list[dict[str, Any]]) -> None:
    if len(options) < 2:
        findings.append(finding(area, "high", f"{label} lacks enough options", {f"{label}_option_count": len(options)}, "Provide at least two options or a documented waiver."))
    option_ids = set()
    for idx, option in enumerate(options):
        if not isinstance(option, dict):
            findings.append(finding(area, "high", f"{label} option must be an object", {"index": idx}, "Use structured option rows."))
            continue
        option_ids.add(option.get("option_id"))
        required = ["option_id", "name", "description", "pros", "cons", "risk_level", "validation", "performance_impact", "rollback_strategy"]
        required.extend(["when_to_choose", "risk_controls"])
        if label == "technical":
            required.extend(["implementation_outline", "test_evidence", "rollout_impact"])
        if label == "architecture":
            required.extend(["owner_repos", "confirm_only_repos", "integration_impact", "deployment_impact", "rollback_complexity"])
        missing = missing_required(option, required)
        if missing:
            findings.append(finding(area, "high", f"{label} option lacks required fields", {"index": idx, "missing": missing}, "Complete option comparison before selecting a solution."))
        for detail_key in ["when_to_choose", "pros", "cons", "risk_controls"]:
            if detail_key in option and len(as_list(option.get(detail_key))) < 2:
                findings.append(finding(area, "medium", f"{label} option {option.get('option_id') or idx} has thin {detail_key}", option.get(detail_key), f"Give at least two concrete {detail_key} entries for each option."))
    selected_id = selected.get("selected_option_id")
    if not selected_id:
        findings.append(finding(area, "high", f"selected {label} option is missing", selected or "selected option empty", "Declare selected_option_id, selection_reason, decision_criteria, and tradeoffs."))
    elif selected_id not in option_ids:
        findings.append(finding(area, "high", f"selected {label} option does not match option list", selected, "Make selected_option_id match an option_id."))
    if selected and not selected.get("decision_criteria"):
        findings.append(finding(area, "medium", f"selected {label} lacks decision criteria", selected, "Record criteria used to choose this option."))
    if selected and not selected.get("tradeoffs"):
        findings.append(finding(area, "medium", f"selected {label} lacks explicit tradeoffs", selected, "Record accepted costs and rejected alternatives."))
    if selected and not selected.get("rejected_alternative_reasoning"):
        findings.append(finding(area, "high", f"selected {label} lacks rejected alternative reasoning", selected, "Record why each non-selected option was rejected before implementation."))


def review_comparison_matrix(matrix: list[Any], score_summary: dict[str, Any], options: list[Any], area: str, label: str, findings: list[dict[str, Any]]) -> None:
    option_ids = {str(item.get("option_id")) for item in options if isinstance(item, dict) and item.get("option_id")}
    if not matrix:
        findings.append(finding(area, "high", f"{label} comparison matrix is missing", f"{label}_comparison empty", "Compare every option across weighted criteria with scores, winner, and reason."))
        return
    compared_options: set[str] = set()
    winners: set[str] = set()
    for idx, row in enumerate(matrix):
        if not isinstance(row, dict):
            findings.append(finding(area, "high", f"{label} comparison row must be an object", {"index": idx}, "Use structured comparison rows."))
            continue
        missing = missing_required(row, ["criterion", "weight", "scores", "winner", "reason"])
        if missing:
            findings.append(finding(area, "high", f"{label} comparison row lacks required fields", {"index": idx, "missing": missing}, "Each row needs criterion, weight, per-option scores, winner, and reason."))
        scores = row.get("scores") if isinstance(row.get("scores"), dict) else {}
        compared_options.update(str(option_id) for option_id in scores)
        winner = str(row.get("winner") or "")
        if winner and winner != "tie":
            winners.add(winner)
        if scores and option_ids and set(scores) != option_ids:
            findings.append(finding(area, "medium", f"{label} comparison row does not score every option", {"index": idx, "expected": sorted(option_ids), "actual": sorted(scores)}, "Score every option in every comparison row."))
        if isinstance(row.get("weight"), int | float) and row.get("weight", 0) <= 0:
            findings.append(finding(area, "medium", f"{label} comparison row has non-positive weight", {"index": idx, "weight": row.get("weight")}, "Use positive weights so criteria importance is explicit."))
    if option_ids and compared_options != option_ids:
        findings.append(finding(area, "high", f"{label} comparison matrix does not cover all options", {"expected": sorted(option_ids), "actual": sorted(compared_options)}, "Every option must appear in the comparison matrix."))
    if len(matrix) < 4:
        findings.append(finding(area, "medium", f"{label} comparison matrix is too shallow", {"criteria_count": len(matrix)}, "Use at least four comparison criteria covering correctness, risk, testability, rollout, and rollback."))
    if not score_summary:
        findings.append(finding(area, "medium", f"{label} score summary is missing", f"{label}_score_summary empty", "Summarize weighted scores so the preferred option is visually obvious."))
    elif option_ids and not option_ids.issubset({str(key) for key in score_summary if key != "scoring_rule"}):
        findings.append(finding(area, "medium", f"{label} score summary does not include every option", score_summary, "Include each option_id in the score summary."))


def review_traceability(req_trace: list[Any], rows: list[Any], area: str, kind: str, findings: list[dict[str, Any]]) -> None:
    req_ids = {item.get("requirement_id") for item in req_trace if isinstance(item, dict) and item.get("requirement_id")}
    row_ids = {item.get("requirement_id") for item in rows if isinstance(item, dict)}
    if not rows:
        findings.append(finding(area, "high", f"{kind} traceability matrix is missing", f"{kind}_traceability empty", "Map every requirement to flow/module/data/API/UI/test/acceptance and option decisions."))
        return
    missing_ids = req_ids - row_ids
    if missing_ids:
        findings.append(finding(area, "high", f"requirements missing from {kind} traceability", sorted(missing_ids), "Add traceability rows for every requirement."))
    for idx, item in enumerate(rows):
        if not isinstance(item, dict):
            findings.append(finding(area, "high", f"{kind} traceability row must be an object", {"index": idx}, "Use structured traceability rows."))
            continue
        if kind == "design":
            required = ["requirement_id", "process_flow_refs", "module_refs", "data_flow_refs", "test_refs", "acceptance_refs", "selected_option_id", "decision_reason"]
            missing = missing_required(item, required)
            if missing:
                findings.append(finding(area, "high", "design traceability row lacks required fields", {"index": idx, "missing": missing}, "Complete design traceability before implementation."))
            if not item.get("api_contract_refs") and not item.get("no_api_reason"):
                findings.append(finding(area, "high", "design traceability lacks API impact decision", {"index": idx}, "Reference API contract or state no API impact reason."))
            if not item.get("ui_ue_refs") and not item.get("no_ui_reason"):
                findings.append(finding(area, "high", "design traceability lacks UI/UX impact decision", {"index": idx}, "Reference UI/UX design or state no UI impact reason."))
        else:
            required = ["requirement_id", "component_boundary_refs", "module_topology_refs", "data_flow_refs", "integration_sequence_refs", "selected_architecture_option_id", "decision_reason"]
            missing = missing_required(item, required)
            if missing:
                findings.append(finding(area, "high", "architecture traceability row lacks required fields", {"index": idx, "missing": missing}, "Complete architecture traceability before implementation."))
            if not item.get("contract_refs") and not item.get("no_cross_repo_reason"):
                findings.append(finding(area, "high", "architecture traceability lacks cross-repo contract decision", {"index": idx}, "Reference cross-repo contract or state no cross-repo reason."))


def review_standalone_readability(
    technical: dict[str, Any],
    architecture: dict[str, Any],
    req_trace: list[Any],
    requirement_breakdown: list[Any],
    current_state: dict[str, Any],
    problem_analysis: dict[str, Any],
    target_behavior: list[Any],
    modules: list[Any],
    technical_options: list[Any],
    selected_solution: dict[str, Any],
    acceptance_mapping: list[Any],
    design_traceability: list[Any],
    current_architecture: dict[str, Any],
    boundaries: list[Any],
    findings: list[dict[str, Any]],
) -> None:
    missing: list[str] = []
    if not req_trace and not requirement_breakdown:
        missing.append("requirement_intent")
    if not current_state and not problem_analysis:
        missing.append("current_state")
    if not target_behavior and not modules:
        missing.append("target_adjustments")
    if not technical_options or not selected_solution.get("selected_option_id"):
        missing.append("implementation_approach")
    if not acceptance_mapping and not design_traceability:
        missing.append("satisfaction_proof")
    if not current_architecture and not boundaries:
        missing.append("engineering_context")
    if missing:
        findings.append(
            finding(
                "standalone_readability_review",
                "high",
                "design cannot be understood standalone",
                {"missing_answers": missing},
                "A reviewer reading only these design artifacts must understand the requirement, current state, target adjustments, implementation approach, and acceptance proof.",
            )
        )


def new_service_signal(technical: dict[str, Any], architecture: dict[str, Any]) -> bool:
    if isinstance(architecture.get("new_service_design"), dict) and architecture.get("new_service_design"):
        return True
    blob = text_of({
        "design_scope": technical.get("design_scope"),
        "architecture_scope": architecture.get("architecture_scope"),
        "architecture_options": architecture.get("architecture_options"),
        "repo_responsibilities": architecture.get("repo_responsibilities"),
        "module_topology": architecture.get("module_topology"),
        "decision_records": architecture.get("decision_records"),
    })
    if any(token in blob for token in ["new service", "new repo", "new repository", "new project", "新服务", "新工程", "新仓库"]):
        return True
    return bool(re.search(r"\b(create|bootstrap|start|add|new)\s+(new\s+)?[a-z0-9_-]+\s+(service|repository|repo|project)\b", blob))


def review_new_service_design(new_service: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    required = [
        "creation_reason",
        "existing_system_fit_analysis",
        "responsibility_boundary",
        "non_responsibilities",
        "technology_stack",
        "repository_bootstrap",
        "module_structure",
        "api_contracts",
        "ci_cd_baseline",
        "configuration_model",
        "deployment_model",
        "observability_baseline",
        "security_baseline",
        "maintenance_ownership",
        "rollout_migration",
        "rollback_strategy",
    ]
    if not new_service:
        findings.append(finding("architecture_boundary_review", "blocker", "new service requirement lacks new_service_design", "new service signal detected", "Explain why a new service/repository is required and define bootstrap, contracts, CI/CD, configuration, deployment, observability, security, ownership, migration, and rollback."))
        return
    missing = missing_required(new_service, required)
    if missing:
        findings.append(finding("architecture_boundary_review", "blocker", "new_service_design lacks expert-grade fields", {"missing": missing}, "Complete the new-service design before architecture approval."))
    if lacks_detail(new_service.get("creation_reason"), 24):
        findings.append(finding("architecture_boundary_review", "high", "new service creation reason is too shallow", new_service.get("creation_reason"), "Compare why existing modules cannot safely own the requirement and why a new service is justified."))
    fit = new_service.get("existing_system_fit_analysis")
    if isinstance(fit, dict):
        fit_missing = missing_required(fit, ["reuse_candidates", "rejected_existing_owners", "decision"])
        if fit_missing:
            findings.append(finding("architecture_boundary_review", "high", "existing system fit analysis is incomplete", {"missing": fit_missing}, "List reuse candidates, rejected existing owners, and the final reuse/new-service decision."))
    elif fit not in (None, "", [], {}):
        findings.append(finding("architecture_boundary_review", "medium", "existing system fit analysis should be structured", fit, "Use reuse_candidates, rejected_existing_owners, and decision fields."))
    nested_requirements = [
        ("repository_bootstrap", "repo_responsibility_review", ["repo_name", "default_branch", "scaffold", "owned_directories", "initial_files"]),
        ("ci_cd_baseline", "deployment_rollback_review", ["build", "test", "package", "deploy", "quality_gates"]),
        ("configuration_model", "deployment_rollback_review", ["environments", "config_sources", "secret_handling", "restart_policy"]),
        ("deployment_model", "deployment_rollback_review", ["artifact", "runtime", "network_entry", "dependency_order", "capacity_baseline"]),
        ("observability_baseline", "observability_review", ["logs", "metrics", "traces", "alerts", "dashboards"]),
        ("security_baseline", "security_review", ["authn", "authz", "tenant_scope", "audit", "data_protection"]),
        ("maintenance_ownership", "repo_responsibility_review", ["owning_team", "oncall", "runbook", "upgrade_policy"]),
        ("rollout_migration", "deployment_rollback_review", ["strategy", "compatibility_window", "cutover", "validation"]),
        ("rollback_strategy", "deployment_rollback_review", ["code", "config", "data", "traffic"]),
    ]
    for key, area, fields in nested_requirements:
        value = new_service.get(key)
        if not isinstance(value, dict):
            if value not in (None, "", [], {}):
                findings.append(finding(area, "high", f"{key} should be structured for new-service design", value, f"Use fields: {', '.join(fields)}."))
            continue
        nested_missing = missing_required(value, fields)
        if nested_missing:
            findings.append(finding(area, "high", f"{key} lacks required new-service fields", {"missing": nested_missing}, f"Complete {key}: {', '.join(fields)}."))


def review(technical: dict[str, Any], architecture: dict[str, Any], ui_ue_artifact: dict[str, Any] | None = None) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    current_state = technical.get("current_state_analysis") if isinstance(technical.get("current_state_analysis"), dict) else {}
    problem_analysis = technical.get("problem_analysis") if isinstance(technical.get("problem_analysis"), dict) else {}
    requirement_breakdown = [item for item in as_list(technical.get("requirement_breakdown")) if isinstance(item, dict)]
    entrypoint_confidence = technical.get("code_entrypoint_confidence") if isinstance(technical.get("code_entrypoint_confidence"), dict) else {}
    req_trace = as_list(technical.get("requirement_trace"))
    target_behavior = as_list(technical.get("target_behavior"))
    business_rules = as_list(technical.get("business_rule_mapping"))
    process_flow = as_list(technical.get("process_flow"))
    modules = as_list(technical.get("module_decomposition"))
    logical_data_flow = as_list(technical.get("logical_data_flow"))
    api_contracts = as_list(technical.get("api_contracts"))
    data_design = as_list(technical.get("data_design"))
    data_model_design = technical.get("data_model_design") if isinstance(technical.get("data_model_design"), dict) else {}
    table_schema_changes = as_list(technical.get("table_schema_changes"))
    system_interaction_sequence = technical.get("system_interaction_sequence") if isinstance(technical.get("system_interaction_sequence"), dict) else {}
    mq_interactions = as_list(technical.get("mq_interactions"))
    cache_strategy = technical.get("cache_strategy") if isinstance(technical.get("cache_strategy"), dict) else {}
    transaction_consistency = technical.get("transaction_consistency") if isinstance(technical.get("transaction_consistency"), dict) else {}
    observability_design = technical.get("observability_design") if isinstance(technical.get("observability_design"), dict) else {}
    permission_model = as_list(technical.get("permission_model"))
    compatibility = as_list(technical.get("compatibility_strategy"))
    edge_cases = as_list(technical.get("exception_and_edge_cases"))
    nfrs = as_list(technical.get("non_functional_requirements"))
    technical_options = as_list(technical.get("solution_options"))
    selected_solution = technical.get("selected_solution") if isinstance(technical.get("selected_solution"), dict) else {}
    option_comparison = as_list(technical.get("option_comparison_matrix"))
    option_score_summary = technical.get("option_score_summary") if isinstance(technical.get("option_score_summary"), dict) else {}
    design_traceability = as_list(technical.get("design_traceability_matrix"))
    acceptance_mapping = as_list(technical.get("acceptance_mapping"))
    ui_ue_design = as_list(technical.get("ui_ue_design"))
    ui_ue_artifact = ui_ue_artifact if isinstance(ui_ue_artifact, dict) else {}
    test_strategy = as_list(technical.get("test_strategy"))
    interface_examples = as_list(technical.get("interface_examples"))
    compatibility_matrix = as_list(technical.get("compatibility_matrix"))
    project_context = technical.get("project_context") if isinstance(technical.get("project_context"), dict) else {}

    current_architecture = architecture.get("current_architecture") if isinstance(architecture.get("current_architecture"), dict) else {}
    arch_entrypoint_confidence = architecture.get("code_entrypoint_confidence") if isinstance(architecture.get("code_entrypoint_confidence"), dict) else {}
    architecture_options = as_list(architecture.get("architecture_options"))
    selected_architecture = architecture.get("selected_architecture") if isinstance(architecture.get("selected_architecture"), dict) else {}
    architecture_fit_matrix = as_list(architecture.get("architecture_fit_matrix"))
    architecture_score_summary = architecture.get("architecture_score_summary") if isinstance(architecture.get("architecture_score_summary"), dict) else {}
    architecture_traceability = as_list(architecture.get("architecture_traceability_matrix"))
    new_service_design = architecture.get("new_service_design") if isinstance(architecture.get("new_service_design"), dict) else {}
    boundaries = as_list(architecture.get("component_boundaries"))
    module_topology = as_list(architecture.get("module_topology"))
    repo_responsibilities = as_list(architecture.get("repo_responsibilities"))
    cross_contracts = as_list(architecture.get("cross_repo_contracts"))
    dependency_graph = as_list(architecture.get("cross_repo_dependency_graph"))
    data_flow = as_list(architecture.get("data_flow"))
    data_ownership = as_list(architecture.get("data_ownership"))
    integration_sequence = as_list(architecture.get("integration_sequence"))
    failure_isolation = as_list(architecture.get("failure_isolation"))
    security_permission = as_list(architecture.get("security_and_permission"))
    observability = as_list(architecture.get("observability"))
    monitoring_alerts = as_list(architecture.get("monitoring_alerts"))
    deployment_topology = as_list(architecture.get("deployment_topology"))
    deployment_matrix = as_list(architecture.get("deployment_impact_matrix"))
    migration_strategy = as_list(architecture.get("migration_strategy"))
    gray_release = as_list(architecture.get("gray_release_strategy"))
    rollback = as_list(architecture.get("rollback_strategy"))
    decision_records = as_list(architecture.get("decision_records"))
    design_blob = text_of({"technical": technical, "architecture": architecture})
    data_signal = has_signal(design_blob, ("database", "table", "field", "schema", "migration", "数据", "字段", "表", "迁移"))
    system_signal = has_signal(design_blob, ("api", "endpoint", "service", "repo", "system", "consumer", "provider", "接口", "服务", "系统", "跨仓", "上下游"))
    mq_signal = has_signal(design_blob, ("mq", "topic", "queue", "producer", "consumer", "message", "event", "kafka", "rocketmq", "rabbitmq", "消息", "队列", "生产者", "消费者"))
    cache_signal = has_signal(design_blob, ("cache", "redis", "ttl", "缓存", "高频", "热点"))
    consistency_signal = has_signal(design_blob, ("transaction", "consistency", "idempot", "rollback", "compensation", "事务", "一致性", "幂等", "补偿", "回滚"))

    review_requirements_understanding_gate(technical, architecture, findings)

    if not isinstance(technical.get("design_scope"), dict) or not technical.get("design_scope", {}).get("in_scope"):
        findings.append(finding("technical_design_quality", "high", "technical design lacks explicit design_scope", technical.get("design_scope"), "Define in_scope, out_of_scope, assumptions, and non_goals."))
    review_standalone_readability(
        technical,
        architecture,
        req_trace,
        requirement_breakdown,
        current_state,
        problem_analysis,
        target_behavior,
        modules,
        technical_options,
        selected_solution,
        acceptance_mapping,
        design_traceability,
        current_architecture,
        boundaries,
        findings,
    )
    if not current_state or missing_required(current_state, ["existing_behavior", "code_entrypoints", "known_constraints"]):
        findings.append(finding("technical_design_quality", "high", "current state analysis is incomplete", current_state, "Describe existing behavior, code entrypoints, constraints, and reuse points before proposing changes."))
    elif lacks_detail(current_state.get("existing_behavior"), 24):
        findings.append(finding("technical_design_quality", "medium", "current state analysis is too shallow", current_state.get("existing_behavior"), "Use concrete repository and behavior facts, not a short generic phrase."))
    if not problem_analysis:
        findings.append(finding("technical_design_quality", "high", "problem_analysis is missing", "problem_analysis empty", "State current behavior, business problem, process gap, constraints, goals, non-goals, and success criteria before options."))
    else:
        missing_problem = missing_required(problem_analysis, ["current_behavior", "business_problem", "process_gap", "code_entrypoints", "constraints", "design_goals", "success_criteria"])
        if missing_problem:
            findings.append(finding("technical_design_quality", "high", "problem_analysis lacks required fields", {"missing": missing_problem}, "Complete problem-specific current-state analysis before option comparison."))
        problem_blob = text_of(problem_analysis)
        if "likely handles the affected behavior" in problem_blob and not problem_analysis.get("business_problem"):
            findings.append(finding("technical_design_quality", "medium", "problem analysis is still template-like", problem_analysis, "Explain the concrete business problem and existing process gap for this requirement."))
    if not req_trace:
        findings.append(finding("requirement_coverage", "blocker", "technical design has no requirement trace", "requirement_trace empty", "Map every requirement to design evidence."))
    if req_trace and len(target_behavior) < len(req_trace):
        findings.append(finding("requirement_coverage", "high", "some requirements lack target behavior", {"requirements": len(req_trace), "target_behavior": len(target_behavior)}, "Add target behavior for each requirement."))
    complexity_signals = len(req_trace) + len(business_rules) + len(requirement_breakdown)
    if complexity_signals >= 5 and len(requirement_breakdown) < 3:
        findings.append(finding("requirement_coverage", "high", "complex requirement lacks business sub-requirement breakdown", {"requirements": len(req_trace), "business_rules": len(business_rules), "breakdown": len(requirement_breakdown)}, "Generate requirement_breakdown from source trace/business rules and map each slice to design sections."))
    if requirement_breakdown:
        for idx, item in enumerate(requirement_breakdown):
            missing = missing_required(item, ["id", "summary", "behavior_change", "impact_areas", "field_impact", "api_impact", "permission_impact"])
            if missing:
                findings.append(finding("requirement_coverage", "high", "requirement breakdown row lacks design-impact fields", {"index": idx, "missing": missing}, "Each sub-requirement needs behavior, field/API/permission impact, and traceability."))
    if requirement_breakdown and len(requirement_breakdown) >= 3 and len(modules) <= 1:
        findings.append(finding("underdesign_risks", "high", "complex requirement is flattened into one module row", {"breakdown_count": len(requirement_breakdown), "module_count": len(modules)}, "Map each major business slice to module responsibility or explicitly justify shared owner-module handling."))
    confidence_level = str(entrypoint_confidence.get("level") or arch_entrypoint_confidence.get("level") or "").lower()
    selected_entrypoint = str(entrypoint_confidence.get("selected_entrypoint") or arch_entrypoint_confidence.get("selected_entrypoint") or "")
    if confidence_level == "low":
        findings.append(finding("technical_design_quality", "high", "primary code entrypoint confidence is low", entrypoint_confidence or arch_entrypoint_confidence, "Inspect project understanding/code index and revise owner module before implementation."))
    elif confidence_level == "medium":
        findings.append(finding("technical_design_quality", "medium", "primary code entrypoint confidence is only medium", entrypoint_confidence or arch_entrypoint_confidence, "Confirm matched entrypoint with adjacent feature code before implementation."))
    if selected_entrypoint and is_generic_entrypoint(selected_entrypoint):
        evidence_text = text_of(entrypoint_confidence.get("evidence") or [])
        if not any(token in evidence_text for token in ["semantic", "route_file", "domain", "feature"]):
            findings.append(finding("technical_design_quality", "high", "generic bootstrap/config/asset file is selected as primary owner entrypoint", selected_entrypoint, "Use feature/service/page/module file as the primary owner or mark the design blocked pending code inspection."))
    if has_placeholder(technical) or has_placeholder(architecture):
        findings.append(finding("technical_design_quality", "medium", "design still contains placeholders", "placeholder detected", "Replace placeholders with concrete decisions."))
    if has_generic_phrase(technical) or has_generic_phrase(architecture):
        findings.append(finding("technical_design_quality", "high", "design contains generic template phrasing", "generic phrase detected", "Replace template phrases with real project files, contracts, owners, and behavior."))
    if not business_rules:
        findings.append(finding("technical_design_quality", "high", "business rules are not mapped to technical enforcement", "business_rule_mapping empty", "Map each business rule to API/service/query/frontend/export enforcement."))
    elif any(isinstance(item, dict) and not (item.get("technical_enforcement") and item.get("source_of_truth")) for item in business_rules):
        findings.append(finding("technical_design_quality", "high", "business rule mapping lacks enforcement or source of truth", business_rules, "Each rule needs technical_enforcement and source_of_truth."))

    review_process_flow(process_flow, findings)
    review_module_decomposition(modules, findings)
    for idx, item in enumerate(modules):
        if isinstance(item, dict) and item.get("module") and not looks_like_path(str(item.get("module"))):
            findings.append(finding("cohesion_coupling_review", "medium", "module reference is not file-level", {"index": idx, "module": item.get("module")}, "Prefer concrete file/module paths from code index for implementation-facing design."))

    if not logical_data_flow:
        findings.append(finding("data_model_review", "high", "logical data flow is missing", "logical_data_flow empty", "Show source, transform, destination, owner, and data-security handling."))
    for idx, item in enumerate(logical_data_flow):
        if isinstance(item, dict):
            missing = missing_required(item, ["source", "transform", "destination", "owner", "data_security"])
            if missing:
                findings.append(finding("data_model_review", "high", "logical data flow lacks required fields", {"index": idx, "missing": missing}, "Add source, transform, destination, owner, and data_security."))

    for idx, item in enumerate(api_contracts):
        if isinstance(item, dict):
            if not (item.get("endpoint") or item.get("field") or item.get("contract")):
                findings.append(finding("api_contract_review", "high", "API contract lacks endpoint/field/contract", {"index": idx}, "Name endpoint, field, compatibility, and old consumer impact."))
            missing = missing_required(item, ["compatibility", "old_consumer_impact"])
            if missing:
                findings.append(finding("api_contract_review", "high", "API contract lacks compatibility fields", {"index": idx, "missing": missing}, "Add compatibility and old_consumer_impact."))
    if api_contracts and not interface_examples:
        findings.append(finding("api_contract_review", "medium", "API/interface examples are missing", "interface_examples empty", "Add request/response/error examples or an explicit no-example reason."))
    if "api" in text_of(technical) and not api_contracts:
        findings.append(finding("api_contract_review", "high", "API-related design lacks API contracts", "api term detected", "Add API contract table or explicit no API impact reason."))

    if not data_design:
        findings.append(finding("data_model_review", "high", "data design is missing", "data_design empty", "Define read/write/null/default/migration semantics or explicitly state no data impact."))
    for idx, item in enumerate(data_design):
        if isinstance(item, dict):
            missing = missing_required(item, ["read_rule", "write_rule", "migration"])
            if missing:
                findings.append(finding("data_model_review", "high", "data design lacks required semantics", {"index": idx, "missing": missing}, "Add read_rule, write_rule, null/default rule, and migration."))

    if data_signal:
        if not data_model_design:
            findings.append(finding("data_model_review", "high", "data-impact design lacks data_model_design", "data signal detected", "Describe affected business entities, fields, ownership, read/write rules, and migration stance."))
        elif data_model_design.get("applicable") is not True and lacks_detail(data_model_design.get("not_applicable_reason"), 18):
            findings.append(finding("data_model_review", "high", "data_model_design is marked not applicable without a concrete reason", data_model_design, "State why no entity/table/field impact exists despite data signals."))
        elif is_applicable(data_model_design):
            missing_model = missing_required(data_model_design, ["entities", "field_rules", "ownership", "read_write_rules", "migration_strategy", "rollback_strategy"])
            if missing_model:
                findings.append(finding("data_model_review", "high", "data_model_design lacks required details", {"missing": missing_model}, "Complete entity, field, owner, read/write, migration, and rollback details."))
            if not table_schema_changes:
                findings.append(finding("data_model_review", "high", "data-impact design lacks table_schema_changes", "table_schema_changes empty", "List table/field/type/null/default/index/migration/rollback or explicitly state no physical schema change."))
    for idx, item in enumerate(table_schema_changes):
        if isinstance(item, dict):
            missing = missing_required(item, ["table", "field", "type", "nullable", "default", "migration", "rollback"])
            if missing:
                findings.append(finding("data_model_review", "high", "table schema change lacks implementation-grade fields", {"index": idx, "missing": missing}, "Each schema row needs table, field, type, nullability, default, migration, and rollback."))

    if system_signal:
        if not system_interaction_sequence:
            findings.append(finding("cross_repo_contract_review", "high", "system interaction sequence is missing", "system/API signal detected", "Describe participants, ordered calls/events, timeout/retry, idempotency, and consistency boundary."))
        elif system_interaction_sequence.get("applicable") is not True and lacks_detail(system_interaction_sequence.get("not_applicable_reason"), 18):
            findings.append(finding("cross_repo_contract_review", "high", "system interaction sequence has no concrete not-applicable reason", system_interaction_sequence, "Explain why this requirement has no multi-module/system interaction."))
        elif is_applicable(system_interaction_sequence):
            missing = missing_required(system_interaction_sequence, ["participants", "sequence", "timeout_retry", "idempotency", "consistency"])
            if missing:
                findings.append(finding("cross_repo_contract_review", "high", "system interaction sequence lacks required fields", {"missing": missing}, "Add participants, ordered sequence, timeout/retry, idempotency, and consistency handling."))

    if mq_signal:
        applicable_mq = [item for item in mq_interactions if isinstance(item, dict) and item.get("applicable") is True]
        if not mq_interactions:
            findings.append(finding("cross_repo_contract_review", "blocker", "MQ/event requirement lacks mq_interactions", "MQ signal detected", "Define producer, consumer, topic/queue, trigger timing, payload, idempotency, retry, and dead-letter/compensation."))
        elif not applicable_mq and not all(isinstance(item, dict) and item.get("applicable") is False and not lacks_detail(item.get("not_applicable_reason") or item.get("reason"), 18) for item in mq_interactions):
            findings.append(finding("cross_repo_contract_review", "high", "MQ/event signal is not backed by an applicable MQ interaction", mq_interactions, "If MQ is only mentioned as non-impact, provide a concrete no-MQ reason; otherwise make one interaction applicable."))
        for idx, item in enumerate(applicable_mq):
            missing = missing_required(item, ["producer", "consumer", "topic_or_queue", "trigger", "payload_fields", "idempotency_key", "retry_policy", "dead_letter_or_compensation"])
            if missing:
                findings.append(finding("cross_repo_contract_review", "blocker", "MQ interaction lacks production-grade fields", {"index": idx, "missing": missing}, "Complete producer/consumer/topic/trigger/payload/idempotency/retry/dead-letter details."))

    if cache_strategy:
        if cache_strategy.get("decision") == "use_cache":
            missing = missing_required(cache_strategy, ["key_design", "value_shape", "ttl", "invalidation", "consistency_risk"])
            if missing:
                findings.append(finding("performance_review", "high", "cache strategy chooses cache without required safeguards", {"missing": missing}, "Define cache key, value shape, TTL, invalidation trigger, and consistency risk."))
    elif cache_signal:
        findings.append(finding("performance_review", "high", "cache-related requirement lacks cache_strategy", "cache signal detected", "State use_cache/no_cache and explain key, TTL, invalidation, and consistency tradeoff."))

    if consistency_signal:
        if not transaction_consistency:
            findings.append(finding("data_model_review", "high", "consistency-sensitive design lacks transaction_consistency", "consistency signal detected", "Define transaction boundary, idempotency, compensation, rollback, and partial failure handling."))
        elif transaction_consistency.get("applicable") is not True and lacks_detail(transaction_consistency.get("not_applicable_reason"), 18):
            findings.append(finding("data_model_review", "high", "transaction consistency is marked not applicable without reason", transaction_consistency, "Explain why no transaction or consistency handling is needed."))
        elif is_applicable(transaction_consistency):
            missing = missing_required(transaction_consistency, ["boundary", "idempotency", "compensation", "rollback"])
            if missing:
                findings.append(finding("data_model_review", "high", "transaction consistency design lacks required fields", {"missing": missing}, "Add boundary, idempotency, compensation, rollback, and partial failure semantics."))

    if not observability_design:
        findings.append(finding("observability_review", "medium", "technical observability design is missing", "observability_design empty", "Define logs, metrics, traces, and alerts for the changed behavior or explicitly waive each one."))
    else:
        missing = missing_required(observability_design, ["logs", "metrics", "traces", "alerts"])
        if missing:
            findings.append(finding("observability_review", "medium", "technical observability design lacks required signals", {"missing": missing}, "Add logs, metrics, traces, and alerts or explicit no-impact reasons."))

    permission_signal = text_of({"requirement_trace": req_trace, "target_behavior": target_behavior, "api_contracts": api_contracts, "design_goal": technical.get("design_goal", "")})
    if any(token in permission_signal for token in ["permission", "tenant", "role", "权限", "租户", "角色", "data scope"]) and not permission_model:
        findings.append(finding("permission_model_review", "blocker", "permission-sensitive design lacks permission_model", "permission terms detected", "Add backend-authoritative permission/data-scope model."))
    if permission_model and has_placeholder(permission_model):
        findings.append(finding("permission_model_review", "high", "permission model is not concrete", permission_model, "Define roles, data scope rules, and negative cases."))

    if not compatibility:
        findings.append(finding("compatibility_review", "high", "compatibility strategy is missing", "compatibility_strategy empty", "Define old consumers, old data, rollback, and additive/breaking behavior."))
    if compatibility and not compatibility_matrix:
        findings.append(finding("compatibility_review", "medium", "compatibility matrix is missing", "compatibility_matrix empty", "Map consumers to old behavior, new behavior, compatibility, and rollback behavior."))
    if not edge_cases:
        findings.append(finding("technical_design_quality", "high", "exception and edge cases are missing", "exception_and_edge_cases empty", "Cover invalid state, permission denial, old consumers, dependency failures, and empty data."))
    if not nfrs:
        findings.append(finding("performance_review", "medium", "non-functional requirements are missing", "non_functional_requirements empty", "State performance/security/compatibility/observability/data consistency impact or explicit waiver."))
    elif "performance" not in text_of(nfrs):
        findings.append(finding("performance_review", "medium", "performance impact is not explicit", nfrs, "Record query/request/latency/cache/export impact or explicit no-impact reason."))
    if not security_permission:
        findings.append(finding("security_review", "medium", "security and permission architecture is missing", "security_and_permission empty", "Define control points or explicitly waive no security impact."))

    review_options(technical_options, selected_solution, "design_depth_review", "technical", findings)
    review_comparison_matrix(option_comparison, option_score_summary, technical_options, "design_depth_review", "technical", findings)
    if any(str(option.get("name", "")).lower() in TEMPLATE_OPTION_NAMES for option in technical_options if isinstance(option, dict)):
        findings.append(finding("design_depth_review", "high", "technical options still use template option names", [option.get("name") for option in technical_options if isinstance(option, dict)], "Generate requirement-specific option names tied to impact area and owner entrypoint."))
    technical_decision_text = text_of({"selected": selected_solution, "options": technical_options, "matrix": option_comparison})
    if any(phrase in technical_decision_text for phrase in TEMPLATE_DECISION_PHRASES):
        findings.append(finding("design_depth_review", "high", "technical option decision uses template rationale", selected_solution, "Decision must follow comparison results and cite requirement-specific evidence."))
    technical_winner = highest_scored_option(option_score_summary)
    if technical_winner and selected_solution.get("selected_option_id") != technical_winner:
        findings.append(finding("design_depth_review", "high", "selected technical option does not match highest weighted score", {"selected": selected_solution.get("selected_option_id"), "highest": technical_winner, "scores": option_score_summary}, "Select the highest weighted option or record an explicit exception with evidence."))
    review_traceability(req_trace, design_traceability, "design_depth_review", "design", findings)

    if not acceptance_mapping:
        findings.append(finding("testability_review", "high", "acceptance criteria are not mapped to evidence", "acceptance_mapping empty", "Map AC ids to design refs and required evidence."))
    elif any(isinstance(item, dict) and not item.get("evidence_required") for item in acceptance_mapping):
        findings.append(finding("testability_review", "high", "acceptance mapping lacks evidence_required", acceptance_mapping, "Each AC needs unit/API/browser/export/permission evidence."))

    frontend_signal = text_of({"frontend_behavior": technical.get("frontend_behavior", []), "requirement_trace": req_trace, "design_goal": technical.get("design_goal", "")})
    if any(token in frontend_signal for token in ["frontend", "ui", "ux", "page", "route", "页面", "按钮", "表格", "弹窗", "前端"]):
        if ui_ue_artifact and ui_ue_artifact.get("decision") == "block":
            findings.append(finding("frontend_behavior_review", "blocker", "independent UI/UE design gate is blocked", ui_ue_artifact.get("blockers"), "Resolve ui_ue_design.json blockers before implementation."))
        if not ui_ue_artifact and not technical.get("ui_ue_design_ref"):
            findings.append(finding("frontend_behavior_review", "low", "frontend requirement lacks independent UI/UE artifact", "ui_ue_design.json missing", "Generate ui_ue_design.json with ui-ue-design-governor before implementation planning."))
        if not ui_ue_design:
            findings.append(finding("frontend_behavior_review", "high", "frontend/UI requirement lacks UI/UX design", "ui_ue_design empty", "Add page/route, user goal, entry point, layout, interaction flow, states, field rules, permission visibility, and acceptance evidence."))
        for idx, item in enumerate(ui_ue_design):
            if isinstance(item, dict):
                missing = missing_required(item, ["page_or_route", "user_goal", "entry_point", "layout", "interaction_flow", "states", "field_rules", "permission_visibility", "acceptance_evidence"])
                if missing:
                    findings.append(finding("frontend_behavior_review", "high", "UI/UX design lacks required fields", {"index": idx, "missing": missing}, "Complete UI/UX design before implementation."))

    if not test_strategy:
        findings.append(finding("testability_review", "blocker", "test strategy is missing", "test_strategy empty", "Add unit/API/UI/permission/export/regression evidence strategy."))
    for idx, hint in enumerate(as_list(project_context.get("test_command_hints"))):
        if isinstance(hint, str) and not executable_command_hint(hint):
            findings.append(finding("testability_review", "medium", "test command hint is not executable", {"index": idx, "hint": hint}, "Use executable commands such as npm test, pytest, mvn test, or document why only manual evidence is available."))

    if not isinstance(architecture.get("architecture_scope"), dict) or not architecture.get("architecture_scope", {}).get("in_scope"):
        findings.append(finding("architecture_boundary_review", "high", "architecture scope is missing", architecture.get("architecture_scope"), "Define architecture in_scope, out_of_scope, assumptions, and decision drivers."))
    if not current_architecture or missing_required(current_architecture, ["system_context", "repo_entrypoints", "upstream_downstream", "constraints"]):
        findings.append(finding("architecture_boundary_review", "high", "current architecture analysis is incomplete", current_architecture, "Describe system context, repo entrypoints, upstream/downstream dependencies, and constraints."))
    elif not any(looks_like_path(str(item)) for item in as_list(current_architecture.get("repo_entrypoints"))):
        findings.append(finding("architecture_boundary_review", "medium", "current architecture lacks concrete repo entrypoint paths", current_architecture.get("repo_entrypoints"), "Use real file, route, or config paths from project understanding."))
    review_options(architecture_options, selected_architecture, "architecture_depth_review", "architecture", findings)
    review_comparison_matrix(architecture_fit_matrix, architecture_score_summary, architecture_options, "architecture_depth_review", "architecture", findings)
    if any(str(option.get("name", "")).lower() in TEMPLATE_OPTION_NAMES for option in architecture_options if isinstance(option, dict)):
        findings.append(finding("architecture_depth_review", "high", "architecture options still use template option names", [option.get("name") for option in architecture_options if isinstance(option, dict)], "Generate architecture options tied to actual owner repo, contract, and data/release risk."))
    architecture_decision_text = text_of({"selected": selected_architecture, "options": architecture_options, "matrix": architecture_fit_matrix})
    if any(phrase in architecture_decision_text for phrase in TEMPLATE_DECISION_PHRASES):
        findings.append(finding("architecture_depth_review", "high", "architecture option decision uses template rationale", selected_architecture, "Architecture decision must follow comparison results and cite owner/contract/data evidence."))
    architecture_winner = highest_scored_option(architecture_score_summary)
    if architecture_winner and selected_architecture.get("selected_option_id") != architecture_winner:
        findings.append(finding("architecture_depth_review", "high", "selected architecture option does not match highest weighted score", {"selected": selected_architecture.get("selected_option_id"), "highest": architecture_winner, "scores": architecture_score_summary}, "Select the highest weighted architecture option or record an explicit exception with evidence."))
    review_traceability(req_trace, architecture_traceability, "architecture_depth_review", "architecture", findings)
    if new_service_signal(technical, architecture):
        review_new_service_design(new_service_design, findings)

    if not boundaries:
        findings.append(finding("architecture_boundary_review", "blocker", "component boundaries are missing", "component_boundaries empty", "Define repo/component roles and exclusions."))
    if not module_topology:
        findings.append(finding("architecture_boundary_review", "high", "module topology is missing", "module_topology empty", "Define repo/module responsibilities, dependencies, boundary rules, and change types."))
    for idx, item in enumerate(module_topology):
        if isinstance(item, dict):
            missing = missing_required(item, ["repo", "module", "responsibility", "depends_on", "boundary_rule", "change_type"])
            if missing:
                findings.append(finding("architecture_boundary_review", "high", "module topology lacks required fields", {"index": idx, "missing": missing}, "Complete module topology before implementation."))

    if not repo_responsibilities:
        findings.append(finding("repo_responsibility_review", "blocker", "repo responsibilities are missing", "repo_responsibilities empty", "Define modify/read_only/confirm_only/out_of_scope responsibilities."))
    for idx, item in enumerate(repo_responsibilities):
        if isinstance(item, dict) and item.get("role") == "modify" and not (item.get("responsibility") or item.get("owner_task")):
            findings.append(finding("repo_responsibility_review", "blocker", "modify repo lacks responsibility", {"index": idx, "repo": item.get("repo")}, "Add concrete owner responsibility."))

    if not cross_contracts:
        findings.append(finding("cross_repo_contract_review", "high", "cross-repo contracts are missing or not explicitly waived", "cross_repo_contracts empty", "Declare contracts or explicitly state no cross-repo contract."))
    if cross_contracts and not dependency_graph:
        findings.append(finding("cross_repo_contract_review", "medium", "cross-repo dependency graph is missing", "cross_repo_dependency_graph empty", "Record producer/consumer direction, contract, and whether each repo is modify or confirm-only."))
    for idx, item in enumerate(cross_contracts):
        if isinstance(item, dict):
            missing = missing_required(item, ["producer", "consumer", "contract", "compatibility", "failure_mode"])
            if missing:
                findings.append(finding("cross_repo_contract_review", "high", "cross-repo contract lacks required fields", {"index": idx, "missing": missing}, "Add producer, consumer, contract, compatibility, and failure_mode."))

    if not data_flow:
        findings.append(finding("data_model_review", "high", "architecture data flow is missing", "data_flow empty", "Describe source, target, scope/filter/null/aggregation rules."))
    if not data_ownership:
        findings.append(finding("data_model_review", "high", "data ownership is missing", "data_ownership empty", "Name owner repo, readers, write authority, and consistency rule."))
    for idx, item in enumerate(data_ownership):
        if isinstance(item, dict):
            missing = missing_required(item, ["business_object", "owner_repo", "write_authority", "consistency_rule"])
            if missing:
                findings.append(finding("data_model_review", "high", "data ownership lacks required fields", {"index": idx, "missing": missing}, "Add business_object, owner_repo, write_authority, and consistency_rule."))

    if not integration_sequence:
        findings.append(finding("cross_repo_contract_review", "high", "integration sequence is missing", "integration_sequence empty", "Describe actor/action/contract/failure handling in execution order."))
    if not failure_isolation:
        findings.append(finding("architecture_depth_review", "medium", "failure isolation design is missing", "failure_isolation empty", "Describe dependency failures, isolation behavior, and user impact."))
    if not rollback:
        findings.append(finding("deployment_rollback_review", "blocker", "rollback strategy is missing", "rollback_strategy empty", "Add repo-specific rollback and data risk."))
    if not observability:
        findings.append(finding("observability_review", "medium", "observability design is missing", "observability empty", "Define logs/metrics/traces or explicitly waive."))
    if not monitoring_alerts:
        findings.append(finding("observability_review", "medium", "monitoring/alert plan is missing", "monitoring_alerts empty", "Define signal, owner, trigger, and action."))
    if not deployment_topology:
        findings.append(finding("deployment_rollback_review", "high", "deployment topology is missing", "deployment_topology empty", "Define repo artifact, environment, and dependencies."))
    if deployment_topology and not deployment_matrix:
        findings.append(finding("deployment_rollback_review", "medium", "deployment impact matrix is missing", "deployment_impact_matrix empty", "List repo, artifact, order, config changes, and restart requirements."))
    if not migration_strategy:
        findings.append(finding("deployment_rollback_review", "high", "migration strategy is missing", "migration_strategy empty", "Define schema/data/config/none and rollback/backward compatibility."))
    if not gray_release:
        findings.append(finding("deployment_rollback_review", "medium", "gray release strategy is missing", "gray_release_strategy empty", "Record feature flag/tenant whitelist/full release and fallback."))
    if not decision_records:
        findings.append(finding("architecture_boundary_review", "medium", "architecture decision records are missing", "decision_records empty", "Record decision, alternatives, and reason."))

    modify_repos = {str(item.get("repo") or f"row-{idx}") for idx, item in enumerate(repo_responsibilities) if isinstance(item, dict) and item.get("role") == "modify"}
    modify_count = len(modify_repos)
    if modify_count > 4:
        findings.append(finding("overengineering_risks", "medium", "many repositories are marked modify", modify_count, "Confirm each modify repo has owner task; downgrade related repos to confirm_only/read_only."))

    score_card = score_findings(findings)
    blockers = [item for item in findings if item["severity"] == "blocker"]
    if blockers:
        decision = "block"
    elif any(item["severity"] in {"high", "medium"} for item in findings):
        decision = "needs_revision"
    else:
        decision = "pass"

    grouped = {area: [item for item in findings if item["area"] == area] for area in REVIEW_AREAS}
    return {
        "schema": "codex-design-architecture-review-v1",
        "score": score_card["score"],
        "level": score_card["level"],
        "severity_counts": score_card["severity_counts"],
        "readiness_gate": {
            "implementation_allowed": decision == "pass" and score_card["score"] >= score_card["minimum_pass_score"],
            "minimum_pass_score": score_card["minimum_pass_score"],
            "expert_ready_score": score_card["expert_ready_score"],
            "rule": "implementation requires decision=pass, score>=85, and no blocker/high/medium findings",
        },
        **grouped,
        "open_questions": as_list(technical.get("open_questions")) + as_list(architecture.get("architecture_risks")),
        "solution_tradeoff_review": {
            "technical": {"options": technical_options, "comparison_matrix": option_comparison, "score_summary": option_score_summary, "selected": selected_solution},
            "architecture": {"options": architecture_options, "comparison_matrix": architecture_fit_matrix, "score_summary": architecture_score_summary, "selected": selected_architecture},
        },
        "blockers": blockers,
        "decision": decision,
    }


def validate(data: dict[str, Any]) -> tuple[bool, list[str]]:
    required = ["schema", "score", "level", "severity_counts", "readiness_gate", "open_questions", "solution_tradeoff_review", "blockers", "decision", *REVIEW_AREAS]
    issues = [f"missing {key}" for key in required if key not in data]
    if data.get("schema") != "codex-design-architecture-review-v1":
        issues.append("schema must be codex-design-architecture-review-v1")
    if data.get("decision") not in {"pass", "needs_revision", "block"}:
        issues.append("decision must be pass/needs_revision/block")
    if data.get("decision") == "pass" and data.get("blockers"):
        issues.append("pass is not allowed with blockers")
    if not isinstance(data.get("score"), int) or not (0 <= data.get("score", -1) <= 100):
        issues.append("score must be integer 0-100")
    if data.get("level") not in {"expert_ready", "reviewable", "needs_revision", "block"}:
        issues.append("level invalid")
    gate = data.get("readiness_gate", {})
    if not isinstance(gate, dict) or "implementation_allowed" not in gate:
        issues.append("readiness_gate.implementation_allowed missing")
    if gate.get("implementation_allowed") and data.get("decision") != "pass":
        issues.append("implementation cannot be allowed unless decision=pass")
    return not issues, issues


def read_json(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"JSON root must be object: {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Design and architecture review gate")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_review = sub.add_parser("review")
    p_review.add_argument("--technical-design", required=True)
    p_review.add_argument("--architecture-design", required=True)
    p_review.add_argument("--ui-ue-design")
    p_review.add_argument("--out")
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--file", required=True)
    args = parser.parse_args()

    if args.cmd == "review":
        result = review(read_json(args.technical_design), read_json(args.architecture_design), read_json(args.ui_ue_design) if args.ui_ue_design else None)
        if args.out:
            Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["decision"] != "block" else 1
    data = read_json(args.file)
    valid, issues = validate(data)
    print(json.dumps({"schema": "codex-design-architecture-review-validation-v1", "valid": valid, "issues": issues}, ensure_ascii=False, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
