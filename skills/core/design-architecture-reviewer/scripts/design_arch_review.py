#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PLACEHOLDERS = ("confirm later", "unknown", "tbd", "todo", "待确认", "后续确认")
PLACEHOLDER_SAFE_KEYS = {"role", "source_evidence", "read_first", "evidence_refs"}
REVIEW_AREAS = [
    "requirement_coverage",
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


def missing_required(item: dict[str, Any], keys: list[str]) -> list[str]:
    return [key for key in keys if key not in item or item.get(key) in (None, "", [])]


def finding(area: str, severity: str, message: str, evidence: Any, suggestion: str) -> dict[str, Any]:
    return {"area": area, "severity": severity, "message": message, "evidence": evidence, "suggestion": suggestion}


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
        if label == "architecture":
            required.extend(["owner_repos", "confirm_only_repos"])
        missing = missing_required(option, required)
        if missing:
            findings.append(finding(area, "high", f"{label} option lacks required fields", {"index": idx, "missing": missing}, "Complete option comparison before selecting a solution."))
    selected_id = selected.get("selected_option_id")
    if not selected_id:
        findings.append(finding(area, "high", f"selected {label} option is missing", selected or "selected option empty", "Declare selected_option_id, selection_reason, decision_criteria, and tradeoffs."))
    elif selected_id not in option_ids:
        findings.append(finding(area, "high", f"selected {label} option does not match option list", selected, "Make selected_option_id match an option_id."))
    if selected and not selected.get("decision_criteria"):
        findings.append(finding(area, "medium", f"selected {label} lacks decision criteria", selected, "Record criteria used to choose this option."))
    if selected and not selected.get("tradeoffs"):
        findings.append(finding(area, "medium", f"selected {label} lacks explicit tradeoffs", selected, "Record accepted costs and rejected alternatives."))


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


def review(technical: dict[str, Any], architecture: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    req_trace = as_list(technical.get("requirement_trace"))
    target_behavior = as_list(technical.get("target_behavior"))
    business_rules = as_list(technical.get("business_rule_mapping"))
    process_flow = as_list(technical.get("process_flow"))
    modules = as_list(technical.get("module_decomposition"))
    logical_data_flow = as_list(technical.get("logical_data_flow"))
    api_contracts = as_list(technical.get("api_contracts"))
    data_design = as_list(technical.get("data_design"))
    permission_model = as_list(technical.get("permission_model"))
    compatibility = as_list(technical.get("compatibility_strategy"))
    edge_cases = as_list(technical.get("exception_and_edge_cases"))
    nfrs = as_list(technical.get("non_functional_requirements"))
    technical_options = as_list(technical.get("solution_options"))
    selected_solution = technical.get("selected_solution") if isinstance(technical.get("selected_solution"), dict) else {}
    design_traceability = as_list(technical.get("design_traceability_matrix"))
    acceptance_mapping = as_list(technical.get("acceptance_mapping"))
    ui_ue_design = as_list(technical.get("ui_ue_design"))
    test_strategy = as_list(technical.get("test_strategy"))

    architecture_options = as_list(architecture.get("architecture_options"))
    selected_architecture = architecture.get("selected_architecture") if isinstance(architecture.get("selected_architecture"), dict) else {}
    architecture_traceability = as_list(architecture.get("architecture_traceability_matrix"))
    boundaries = as_list(architecture.get("component_boundaries"))
    module_topology = as_list(architecture.get("module_topology"))
    repo_responsibilities = as_list(architecture.get("repo_responsibilities"))
    cross_contracts = as_list(architecture.get("cross_repo_contracts"))
    data_flow = as_list(architecture.get("data_flow"))
    data_ownership = as_list(architecture.get("data_ownership"))
    integration_sequence = as_list(architecture.get("integration_sequence"))
    security_permission = as_list(architecture.get("security_and_permission"))
    observability = as_list(architecture.get("observability"))
    monitoring_alerts = as_list(architecture.get("monitoring_alerts"))
    deployment_topology = as_list(architecture.get("deployment_topology"))
    migration_strategy = as_list(architecture.get("migration_strategy"))
    gray_release = as_list(architecture.get("gray_release_strategy"))
    rollback = as_list(architecture.get("rollback_strategy"))
    decision_records = as_list(architecture.get("decision_records"))

    if not isinstance(technical.get("design_scope"), dict) or not technical.get("design_scope", {}).get("in_scope"):
        findings.append(finding("technical_design_quality", "high", "technical design lacks explicit design_scope", technical.get("design_scope"), "Define in_scope, out_of_scope, assumptions, and non_goals."))
    if not req_trace:
        findings.append(finding("requirement_coverage", "blocker", "technical design has no requirement trace", "requirement_trace empty", "Map every requirement to design evidence."))
    if req_trace and len(target_behavior) < len(req_trace):
        findings.append(finding("requirement_coverage", "high", "some requirements lack target behavior", {"requirements": len(req_trace), "target_behavior": len(target_behavior)}, "Add target behavior for each requirement."))
    if has_placeholder(technical) or has_placeholder(architecture):
        findings.append(finding("technical_design_quality", "medium", "design still contains placeholders", "placeholder detected", "Replace placeholders with concrete decisions."))
    if not business_rules:
        findings.append(finding("technical_design_quality", "high", "business rules are not mapped to technical enforcement", "business_rule_mapping empty", "Map each business rule to API/service/query/frontend/export enforcement."))
    elif any(isinstance(item, dict) and not (item.get("technical_enforcement") and item.get("source_of_truth")) for item in business_rules):
        findings.append(finding("technical_design_quality", "high", "business rule mapping lacks enforcement or source of truth", business_rules, "Each rule needs technical_enforcement and source_of_truth."))

    review_process_flow(process_flow, findings)
    review_module_decomposition(modules, findings)

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
    if "api" in text_of(technical) and not api_contracts:
        findings.append(finding("api_contract_review", "high", "API-related design lacks API contracts", "api term detected", "Add API contract table or explicit no API impact reason."))

    if not data_design:
        findings.append(finding("data_model_review", "high", "data design is missing", "data_design empty", "Define read/write/null/default/migration semantics or explicitly state no data impact."))
    for idx, item in enumerate(data_design):
        if isinstance(item, dict):
            missing = missing_required(item, ["read_rule", "write_rule", "migration"])
            if missing:
                findings.append(finding("data_model_review", "high", "data design lacks required semantics", {"index": idx, "missing": missing}, "Add read_rule, write_rule, null/default rule, and migration."))

    permission_signal = text_of({"requirement_trace": req_trace, "target_behavior": target_behavior, "api_contracts": api_contracts, "design_goal": technical.get("design_goal", "")})
    if any(token in permission_signal for token in ["permission", "tenant", "role", "权限", "租户", "角色", "data scope"]) and not permission_model:
        findings.append(finding("permission_model_review", "blocker", "permission-sensitive design lacks permission_model", "permission terms detected", "Add backend-authoritative permission/data-scope model."))
    if permission_model and has_placeholder(permission_model):
        findings.append(finding("permission_model_review", "high", "permission model is not concrete", permission_model, "Define roles, data scope rules, and negative cases."))

    if not compatibility:
        findings.append(finding("compatibility_review", "high", "compatibility strategy is missing", "compatibility_strategy empty", "Define old consumers, old data, rollback, and additive/breaking behavior."))
    if not edge_cases:
        findings.append(finding("technical_design_quality", "high", "exception and edge cases are missing", "exception_and_edge_cases empty", "Cover invalid state, permission denial, old consumers, dependency failures, and empty data."))
    if not nfrs:
        findings.append(finding("performance_review", "medium", "non-functional requirements are missing", "non_functional_requirements empty", "State performance/security/compatibility/observability/data consistency impact or explicit waiver."))
    elif "performance" not in text_of(nfrs):
        findings.append(finding("performance_review", "medium", "performance impact is not explicit", nfrs, "Record query/request/latency/cache/export impact or explicit no-impact reason."))
    if not security_permission:
        findings.append(finding("security_review", "medium", "security and permission architecture is missing", "security_and_permission empty", "Define control points or explicitly waive no security impact."))

    review_options(technical_options, selected_solution, "design_depth_review", "technical", findings)
    review_traceability(req_trace, design_traceability, "design_depth_review", "design", findings)

    if not acceptance_mapping:
        findings.append(finding("testability_review", "high", "acceptance criteria are not mapped to evidence", "acceptance_mapping empty", "Map AC ids to design refs and required evidence."))
    elif any(isinstance(item, dict) and not item.get("evidence_required") for item in acceptance_mapping):
        findings.append(finding("testability_review", "high", "acceptance mapping lacks evidence_required", acceptance_mapping, "Each AC needs unit/API/browser/export/permission evidence."))

    frontend_signal = text_of({"frontend_behavior": technical.get("frontend_behavior", []), "requirement_trace": req_trace, "design_goal": technical.get("design_goal", "")})
    if any(token in frontend_signal for token in ["frontend", "ui", "ux", "page", "route", "页面", "按钮", "表格", "弹窗", "前端"]):
        if not ui_ue_design:
            findings.append(finding("frontend_behavior_review", "high", "frontend/UI requirement lacks UI/UX design", "ui_ue_design empty", "Add page/route, user goal, entry point, layout, interaction flow, states, field rules, permission visibility, and acceptance evidence."))
        for idx, item in enumerate(ui_ue_design):
            if isinstance(item, dict):
                missing = missing_required(item, ["page_or_route", "user_goal", "entry_point", "layout", "interaction_flow", "states", "field_rules", "permission_visibility", "acceptance_evidence"])
                if missing:
                    findings.append(finding("frontend_behavior_review", "high", "UI/UX design lacks required fields", {"index": idx, "missing": missing}, "Complete UI/UX design before implementation."))

    if not test_strategy:
        findings.append(finding("testability_review", "blocker", "test strategy is missing", "test_strategy empty", "Add unit/API/UI/permission/export/regression evidence strategy."))

    if not isinstance(architecture.get("architecture_scope"), dict) or not architecture.get("architecture_scope", {}).get("in_scope"):
        findings.append(finding("architecture_boundary_review", "high", "architecture scope is missing", architecture.get("architecture_scope"), "Define architecture in_scope, out_of_scope, assumptions, and decision drivers."))
    review_options(architecture_options, selected_architecture, "architecture_depth_review", "architecture", findings)
    review_traceability(req_trace, architecture_traceability, "architecture_depth_review", "architecture", findings)

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
    if not rollback:
        findings.append(finding("deployment_rollback_review", "blocker", "rollback strategy is missing", "rollback_strategy empty", "Add repo-specific rollback and data risk."))
    if not observability:
        findings.append(finding("observability_review", "medium", "observability design is missing", "observability empty", "Define logs/metrics/traces or explicitly waive."))
    if not monitoring_alerts:
        findings.append(finding("observability_review", "medium", "monitoring/alert plan is missing", "monitoring_alerts empty", "Define signal, owner, trigger, and action."))
    if not deployment_topology:
        findings.append(finding("deployment_rollback_review", "high", "deployment topology is missing", "deployment_topology empty", "Define repo artifact, environment, and dependencies."))
    if not migration_strategy:
        findings.append(finding("deployment_rollback_review", "high", "migration strategy is missing", "migration_strategy empty", "Define schema/data/config/none and rollback/backward compatibility."))
    if not gray_release:
        findings.append(finding("deployment_rollback_review", "medium", "gray release strategy is missing", "gray_release_strategy empty", "Record feature flag/tenant whitelist/full release and fallback."))
    if not decision_records:
        findings.append(finding("architecture_boundary_review", "medium", "architecture decision records are missing", "decision_records empty", "Record decision, alternatives, and reason."))

    modify_count = sum(1 for item in repo_responsibilities if isinstance(item, dict) and item.get("role") == "modify")
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
            "technical": {"options": technical_options, "selected": selected_solution},
            "architecture": {"options": architecture_options, "selected": selected_architecture},
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
    p_review.add_argument("--out")
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--file", required=True)
    args = parser.parse_args()

    if args.cmd == "review":
        result = review(read_json(args.technical_design), read_json(args.architecture_design))
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
