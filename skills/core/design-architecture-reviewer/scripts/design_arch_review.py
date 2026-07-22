#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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
DOMAIN_LEAK_TERMS = (
    "播放器资源",
    "播放器生命周期",
    "player resources",
    "player lifecycle",
)
PERSISTENCE_REQUIRED_TERMS = (
    "审批记录", "审批状态", "审批结果", "实例号", "失败原因", "回调", "建单", "结算单",
    "批次", "落库", "记录表", "状态机",
    "approval record", "approval status", "failure reason", "callback", "retry count", "settlement",
    "idempotency key", "state machine",
)
EXTERNAL_PROVIDER_API_PATTERNS = (
    "/open-apis/",
    "external_access_token",
    "provider_access_token",
)
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


def has_any_signal(blob: str, terms: tuple[str, ...]) -> bool:
    lower = blob.lower()
    return any(term.lower() in lower or term in blob for term in terms)


def is_external_provider_contract(value: str) -> bool:
    lower = value.lower()
    return any(pattern in lower for pattern in EXTERNAL_PROVIDER_API_PATTERNS)


def strip_non_trigger_explanation(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: strip_non_trigger_explanation(item)
            for key, item in value.items()
            if key not in {"not_applicable_reason"}
        }
    if isinstance(value, list):
        return [strip_non_trigger_explanation(item) for item in value]
    return value


def finding(area: str, severity: str, message: str, evidence: Any, suggestion: str) -> dict[str, Any]:
    return {"area": area, "severity": severity, "message": message, "evidence": evidence, "suggestion": suggestion}


def normalized_text(value: Any) -> str:
    return re.sub(r"\s+", " ", meaningful_text(value)).strip().lower()


def token_set(value: Any) -> set[str]:
    return {item for item in re.findall(r"[a-z0-9\u4e00-\u9fff]+", normalized_text(value)) if len(item) >= 2}


def similarity_ratio(left: Any, right: Any) -> float:
    left_tokens = token_set(left)
    right_tokens = token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(len(left_tokens), len(right_tokens))


def literal_value(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("literal") or item.get("value") or item.get("term") or "")
    return str(item or "")


def literal_mapping_notes(*sources: dict[str, Any]) -> list[dict[str, Any]]:
    notes: list[dict[str, Any]] = []
    for source in sources:
        for key in ("source_literal_mapping_notes", "literal_mappings", "literal_mapping_notes", "status_literal_mappings"):
            for item in as_list(source.get(key)):
                if isinstance(item, dict):
                    notes.append(item)
    return notes


def mapping_covers_variant(literal: str, variant: str, mappings: list[dict[str, Any]]) -> bool:
    literal_upper = literal.upper()
    variant_upper = variant.upper()
    for item in mappings:
        source_literal = str(item.get("source_literal") or item.get("literal") or item.get("from") or "").upper()
        variants = [str(value).upper() for value in as_list(item.get("design_variants") or item.get("variants") or item.get("to"))]
        mapping_rule = str(item.get("mapping_rule") or item.get("rule") or item.get("reason") or item.get("not_same_reason") or "")
        rule_upper = mapping_rule.upper()
        if source_literal != literal_upper:
            continue
        variant_covered = variant_upper in variants or variant_upper in rule_upper
        literal_covered = literal_upper in rule_upper or source_literal == literal_upper
        explicit_boundary = any(term in mapping_rule for term in ("不是同一", "不允许混用", "禁止混用", "不同状态", "different", "not the same", "do not mix", "separate"))
        if variant_covered and literal_covered and (mapping_rule.strip() or explicit_boundary):
            return True
    return False


def critical_source_literals(technical: dict[str, Any]) -> list[str]:
    literals = [literal_value(item).strip() for item in as_list(technical.get("source_literals"))]
    if not literals:
        source_blob = text_of({
            "requirement_trace": technical.get("requirement_trace"),
            "business_rule_mapping": technical.get("business_rule_mapping"),
            "acceptance_mapping": technical.get("acceptance_mapping"),
            "target_behavior": technical.get("target_behavior"),
        })
        literals.extend(re.findall(r"/[A-Za-z0-9_./{}:-]+", source_blob))
        literals.extend(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", source_blob))
    result: list[str] = []
    for literal in literals:
        clean = literal.strip(".,;:，。；：)）]】\"'")
        if len(clean) >= 3 and clean.lower() not in {"api", "req", "rule"} and clean not in result:
            result.append(clean)
    return result[:80]


def review_acceptance_literal_guard(technical: dict[str, Any], architecture: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    literals = critical_source_literals(technical)
    if not literals:
        return
    design_blob = text_of({"technical": technical, "architecture": architecture})
    raw_design_blob = json.dumps({"technical": technical, "architecture": architecture}, ensure_ascii=False)
    raw_mappings_blob = json.dumps({
        "requirement_breakdown": technical.get("requirement_breakdown"),
        "business_rule_mapping": technical.get("business_rule_mapping"),
        "acceptance_mapping": technical.get("acceptance_mapping"),
        "api_contracts": technical.get("api_contracts"),
    }, ensure_ascii=False)
    explicit_mappings = literal_mapping_notes(technical, architecture)
    mapped_upper_literals = set(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", raw_mappings_blob.upper()))
    missing = []
    drifted = []
    for literal in literals:
        low = literal.lower()
        if low not in design_blob:
            missing.append(literal)
            continue
        if re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", literal):
            related = [match for match in re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", raw_design_blob) if literal in match and match != literal]
            unmapped_related = [
                match for match in sorted(set(related))
                if not mapping_covers_variant(literal, match, explicit_mappings)
            ]
            if unmapped_related and literal not in mapped_upper_literals:
                drifted.append({"source_literal": literal, "design_variants": unmapped_related[:5]})
    if missing:
        findings.append(finding(
            "requirement_coverage",
            "high",
            "source requirement literals are not bound in design",
            missing[:20],
            "Carry exact enum/status/API/field/time-window literals from source into rule, contract, data, acceptance, or explicit no-impact mappings.",
        ))
    if drifted:
        findings.append(finding(
            "requirement_coverage",
            "high",
            "source literals appear rewritten without an explicit mapping",
            drifted[:20],
            "Do not rewrite source enum/status literals such as EXPIRING into derived labels unless the mapping is explicitly justified.",
        ))


def collect_constraint_patterns(technical: dict[str, Any], architecture: dict[str, Any]) -> dict[str, list[str]]:
    result = {
        "forbidden_reuse_paths": [],
        "forbidden_modules": [],
        "forbidden_contracts": [],
        "forbidden_behaviors": [],
        "out_of_scope_patterns": [],
    }
    for source in [technical, architecture]:
        model = source.get("constraint_model") if isinstance(source.get("constraint_model"), dict) else {}
        for key in result:
            values = [*as_list(source.get(key)), *as_list(model.get(key))]
            for value in values:
                if isinstance(value, dict):
                    candidate = value.get("pattern") or value.get("value") or value.get("path") or value.get("contract") or value.get("behavior") or value.get("summary") or value.get("name")
                else:
                    candidate = value
                text = str(candidate or "").strip()
                if text and text not in result[key]:
                    result[key].append(text)
    return result


def implementation_surface_for_constraint_review(technical: dict[str, Any], architecture: dict[str, Any]) -> dict[str, Any]:
    return {
        "module_decomposition": technical.get("module_decomposition"),
        "api_contracts": technical.get("api_contracts"),
        "logical_data_flow": technical.get("logical_data_flow"),
        "system_interaction_sequence": technical.get("system_interaction_sequence"),
        "selected_solution": technical.get("selected_solution"),
        "solution_options": technical.get("solution_options"),
        "data_design": technical.get("data_design"),
        "ui_ue_design": technical.get("ui_ue_design"),
        "module_topology": architecture.get("module_topology"),
        "repo_responsibilities": architecture.get("repo_responsibilities"),
        "cross_repo_contracts": architecture.get("cross_repo_contracts"),
        "integration_sequence": architecture.get("integration_sequence"),
        "data_flow": architecture.get("data_flow"),
        "deployment_topology": architecture.get("deployment_topology"),
        "rollback_strategy": architecture.get("rollback_strategy"),
        "selected_architecture": architecture.get("selected_architecture"),
        "architecture_options": architecture.get("architecture_options"),
    }


def review_generic_constraints(technical: dict[str, Any], architecture: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    patterns_by_key = collect_constraint_patterns(technical, architecture)
    surface_blob = text_of(implementation_surface_for_constraint_review(technical, architecture))
    violations: list[dict[str, str]] = []
    for key, patterns in patterns_by_key.items():
        for pattern in patterns:
            normalized = normalized_text(pattern)
            if len(normalized) < 3:
                continue
            if normalized in surface_blob:
                violations.append({"constraint_type": key, "pattern": pattern})
    if violations:
        findings.append(finding(
            "requirement_coverage",
            "blocker",
            "implementation-facing design violates requirement-provided forbidden or out-of-scope constraints",
            violations[:30],
            "Remove forbidden/out-of-scope modules, paths, contracts, or behaviors from implementation-facing sections, or update the requirement constraint model with explicit approval.",
        ))


def expected_repositories_from_design(technical: dict[str, Any], architecture: dict[str, Any]) -> set[str]:
    expected: set[str] = set()
    for source in [technical, architecture]:
        repo_map_raw = source.get("repo_impact_map")
        repo_map = repo_map_raw if isinstance(repo_map_raw, dict) else {}
        if not repo_map:
            gate_raw = source.get("requirements_understanding_gate")
            gate = gate_raw if isinstance(gate_raw, dict) else {}
            repo_map_raw = gate.get("repo_impact_map")
            repo_map = repo_map_raw if isinstance(repo_map_raw, dict) else {}
        for item in as_list(repo_map.get("repos") if isinstance(repo_map, dict) else []):
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                if name:
                    expected.add(name)
        scope_raw = source.get("design_scope")
        scope = scope_raw if isinstance(scope_raw, dict) else {}
        for item in as_list(scope.get("declared_roles")):
            if isinstance(item, dict):
                repo = str(item.get("repo") or item.get("repository") or "").strip()
                path = str(item.get("path") or "")
                if repo:
                    expected.add(repo)
                elif path.startswith("src/") or path.endswith((".vue", ".tsx", ".jsx")):
                    continue
    design_text = text_of({"technical": technical, "architecture": architecture})
    for repo in re.findall(r"\b[A-Za-z0-9_-]+(?:-platform-fe|-fe|-[Ff]rontend)\b", design_text):
        expected.add(repo)
    return expected


def review_semantic_hygiene(
    technical: dict[str, Any],
    architecture: dict[str, Any],
    api_contracts: list[Any],
    data_model_design: dict[str, Any],
    repo_responsibilities: list[Any],
    data_excluded: bool,
    findings: list[dict[str, Any]],
) -> None:
    design_text = json.dumps(strip_non_trigger_explanation({"technical": technical, "architecture": architecture}), ensure_ascii=False)
    leaks = sorted({term for term in DOMAIN_LEAK_TERMS if term.lower() in design_text.lower()})
    if leaks:
        findings.append(finding(
            "technical_design_quality",
            "blocker",
            "design contains cross-domain leaked terms",
            leaks,
            "Remove stale terms from other requirements and regenerate the affected design/docs artifacts before review.",
        ))

    persistence_required = has_any_signal(design_text, PERSISTENCE_REQUIRED_TERMS)
    if persistence_required and (data_excluded or data_model_design.get("applicable") is False):
        findings.append(finding(
            "data_model_review",
            "blocker",
            "design claims no persistence impact while requirement needs records, states, callbacks, retries, or idempotency",
            {"data_excluded": data_excluded, "data_model_design": data_model_design},
            "Generate data-model design with entities, fields, indexes, migration/no-migration evidence, read/write rules, and rollback strategy before review.",
        ))

    provider_contracts = [
        item for item in api_contracts
        if isinstance(item, dict)
        and is_external_provider_contract(str(item.get("endpoint") or item.get("contract") or ""))
    ]
    if provider_contracts:
        findings.append(finding(
            "api_contract_review",
            "blocker",
            "external provider API is used as a local system API contract",
            provider_contracts[:10],
            "Classify provider APIs under external_provider_contracts and bind local controllers/routes separately for implementation and testing.",
        ))

    expected_repos = expected_repositories_from_design(technical, architecture)
    planned_repos = {
        str(item.get("repo") or "").strip()
        for item in repo_responsibilities
        if isinstance(item, dict) and str(item.get("repo") or "").strip()
    }
    missing_repos = sorted(repo for repo in expected_repos if repo not in planned_repos)
    if missing_repos:
        findings.append(finding(
            "repo_responsibility_review",
            "blocker",
            "repo responsibilities do not cover all requirement-declared repositories",
            {"expected": sorted(expected_repos), "planned": sorted(planned_repos), "missing": missing_repos},
            "Regenerate architecture and delivery planning so every declared owner/consumer/frontend/backend repository is represented with modify/read_only/confirm_only/out_of_scope role.",
        ))


def artifact_digest(data: dict[str, Any]) -> str:
    def strip_volatile(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: strip_volatile(item)
                for key, item in sorted(value.items())
                if key not in {"generated_at", "updated_at", "producer", "producer_version", "lineage_schema", "input_digests"}
            }
        if isinstance(value, list):
            return [strip_volatile(item) for item in value]
        return value

    payload = json.dumps(strip_volatile(data), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def review_specialty_artifacts(specialty_artifacts: dict[str, dict[str, Any]], findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    area_by_name = {
        "ui_ue_review.json": "frontend_behavior_review",
        "api_contract_design.json": "api_contract_review",
        "data_model_design.json": "data_model_review",
        "observability_design.json": "observability_review",
        "configuration_readiness.json": "deployment_rollback_review",
        "data_security_review.json": "security_review",
        "performance_review.json": "performance_review",
        "cross_repo_readiness.json": "cross_repo_contract_review",
        "test_design.json": "testability_review",
    }
    summary: list[dict[str, Any]] = []
    blocking_decisions = {"block", "blocked", "fail", "failed", "needs_revision", "no_go"}
    accepted_decisions = {"", "pass", "ready", "not_applicable", "skipped"}
    evidence_pending_decisions = {"needs_review", "needs_evidence", "ready_with_advisory", "conditional"}
    for name, artifact in specialty_artifacts.items():
        if not artifact:
            continue
        decision = str(artifact.get("decision") or artifact.get("status") or "")
        blockers = as_list(artifact.get("blockers")) + as_list(artifact.get("active_blockers"))
        applicable = artifact.get("applicable")
        not_applicable = applicable is False or decision == "not_applicable"
        summary.append({"artifact": name, "decision": decision, "applicable": applicable, "blocker_count": len(blockers)})
        if not_applicable:
            continue
        if blockers or decision in blocking_decisions:
            findings.append(finding(
                area_by_name.get(name, "technical_design_quality"),
                "blocker",
                f"specialty design gate {name} is not approved",
                {"decision": decision, "blockers": blockers},
                "Resolve the specialty design findings and regenerate dependent technical, architecture, test, and delivery artifacts.",
            ))
        elif decision in evidence_pending_decisions:
            findings.append(finding(
                area_by_name.get(name, "technical_design_quality"),
                "low",
                f"specialty design gate {name} needs follow-up evidence",
                {"decision": decision, "blockers": blockers},
                "Carry the specialty evidence requirement into implementation, test, or release evidence without blocking design approval by itself.",
            ))
        elif decision not in accepted_decisions:
            findings.append(finding(
                area_by_name.get(name, "technical_design_quality"),
                "medium",
                f"specialty design gate {name} has unrecognized non-blocking decision",
                {"decision": decision, "blockers": blockers},
                "Normalize the specialty gate decision to pass, ready, not_applicable, needs_evidence, needs_review, or block.",
            ))
    return summary


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


def review_local_project_binding(technical: dict[str, Any], architecture: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    technical_binding = technical.get("local_project_binding")
    if not isinstance(technical_binding, dict):
        technical_binding = (technical.get("project_context") or {}).get("local_project_binding") if isinstance(technical.get("project_context"), dict) else {}
    architecture_binding = architecture.get("local_project_binding") if isinstance(architecture.get("local_project_binding"), dict) else {}
    binding = technical_binding if isinstance(technical_binding, dict) and technical_binding else architecture_binding
    if not binding:
        project_context = technical.get("project_context") if isinstance(technical.get("project_context"), dict) else {}
        source_locations = technical.get("source_location_evidence") if isinstance(technical.get("source_location_evidence"), dict) else architecture.get("source_location_evidence") if isinstance(architecture.get("source_location_evidence"), dict) else {}
        repo_evidence_present = bool(project_context.get("repo_root") or source_locations.get("repo_root"))
        if repo_evidence_present:
            findings.append(finding(
                "architecture_boundary_review",
                "blocker",
                "repository-backed design lacks local project binding",
                {"project_context": project_context, "source_location_repo_root": source_locations.get("repo_root")},
                "Regenerate source-location evidence and design so local_project_binding records repo root, Git branch/head, and project skill overlay loading.",
            ))
        return

    if binding.get("project_skill_required") and not binding.get("project_skill_loaded"):
        findings.append(finding(
            "architecture_boundary_review",
            "blocker",
            "design did not load the local project skill overlay",
            binding,
            "Load the installed company project skill and regenerate source-location evidence before technical or architecture design.",
        ))
    git = binding.get("git") if isinstance(binding.get("git"), dict) else {}
    if binding.get("repo_root") and git.get("status") != "ready":
        findings.append(finding(
            "repo_responsibility_review",
            "blocker",
            "design is not bound to a Git worktree",
            binding,
            "Run repository-backed intake from the real local repo and capture Git branch/head before design.",
        ))
    if binding.get("repo_root") and not (git.get("branch") and git.get("head")):
        findings.append(finding(
            "repo_responsibility_review",
            "blocker",
            "design lacks current Git branch or HEAD binding",
            binding,
            "Regenerate project understanding/source-location evidence so design records the current branch and commit.",
        ))
    if technical_binding and architecture_binding and technical_binding != architecture_binding:
        findings.append(finding(
            "architecture_boundary_review",
            "blocker",
            "technical and architecture design use different local project bindings",
            {"technical": technical_binding, "architecture": architecture_binding},
            "Regenerate architecture design from the current technical design and project evidence instead of mixing stale artifacts.",
        ))


def review_architecture_routing_evidence(architecture: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    confidence = architecture.get("architecture_decision_confidence") if isinstance(architecture.get("architecture_decision_confidence"), dict) else {}
    reducers = as_list(confidence.get("confidence_reducers"))
    risks = as_list(architecture.get("architecture_risks"))
    routing_blob = text_of({"confidence_reducers": reducers, "architecture_risks": risks})
    if "owner repo not yet routed" in routing_blob or "owner repo path is not routed" in routing_blob:
        findings.append(finding(
            "repo_responsibility_review",
            "blocker",
            "architecture says owner repo path is not routed",
            {"architecture_decision_confidence": confidence, "architecture_risks": risks},
            "Do not pass design review until the owner repo path is concrete and matches delivery plan/git evidence.",
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


def review_process_flow_diagram(process_flow: list[Any], diagram: Any, findings: list[dict[str, Any]]) -> None:
    if not process_flow:
        return
    text = str(diagram or "").strip()
    if not text:
        findings.append(finding("technical_design_quality", "blocker", "process flow diagram is missing", "process_flow_diagram empty", "Render a Mermaid flowchart from the reviewed business flow."))
        return
    if "```mermaid" not in text.lower() or "flowchart" not in text.lower():
        findings.append(finding("technical_design_quality", "high", "process flow diagram must be a Mermaid flowchart", diagram, "Use Mermaid flowchart syntax so downstream docs and review can reuse it."))
        return
    normalized_diagram = normalized_text(text)
    for flow in process_flow:
        if not isinstance(flow, dict):
            continue
        for step in as_list(flow.get("steps")):
            if not isinstance(step, dict):
                continue
            action = normalized_text(step.get("action"))
            actor = normalized_text(step.get("actor"))
            if action and action not in normalized_diagram:
                findings.append(finding("technical_design_quality", "high", "process flow diagram misses a structured step action", {"actor": step.get("actor"), "action": step.get("action")}, "Keep the Mermaid flowchart aligned with structured process_flow steps."))
            if actor and actor not in normalized_diagram:
                findings.append(finding("technical_design_quality", "medium", "process flow diagram misses a structured actor", {"actor": step.get("actor")}, "Show the actor for each major business step in the Mermaid flowchart."))


def review_system_sequence_diagram(system_interaction_sequence: dict[str, Any], diagram: Any, findings: list[dict[str, Any]]) -> None:
    if not is_applicable(system_interaction_sequence):
        return
    text = str(diagram or "").strip()
    if not text:
        findings.append(finding("cross_repo_contract_review", "blocker", "system sequence diagram is missing", "system_sequence_diagram empty", "Render a Mermaid sequence diagram from the reviewed system interaction sequence."))
        return
    if "```mermaid" not in text.lower() or "sequencediagram" not in text.lower():
        findings.append(finding("cross_repo_contract_review", "high", "system sequence diagram must be Mermaid sequenceDiagram", diagram, "Use Mermaid sequenceDiagram syntax so review can compare it with structured sequence data."))
        return
    participants = [str(item) for item in as_list(system_interaction_sequence.get("participants")) if item]
    steps = as_list(system_interaction_sequence.get("sequence"))
    normalized_diagram = normalized_text(text)
    if len(steps) < 2:
        findings.append(finding("cross_repo_contract_review", "high", "system interaction sequence is too shallow", {"step_count": len(steps)}, "Model at least request, downstream interaction, and completion/error handling steps."))
    for participant in participants:
        if normalized_text(participant) not in normalized_diagram:
            findings.append(finding("cross_repo_contract_review", "medium", "system sequence diagram misses a participant", participant, "Show every reviewed participant in the Mermaid sequence diagram."))
    for idx, step in enumerate(steps):
        if not isinstance(step, dict):
            findings.append(finding("cross_repo_contract_review", "high", "system interaction sequence step must be structured", {"index": idx, "value": step}, "Represent sequence steps as objects with from/to/action/success/failure/state_transition/source_evidence."))
            continue
        missing = missing_required(step, ["step", "from", "to", "action", "success", "failure", "state_transition", "source_evidence"])
        if missing:
            findings.append(finding("cross_repo_contract_review", "high", "system interaction sequence step lacks required fields", {"index": idx, "missing": missing}, "Complete each sequence step before design approval."))
            continue
        for key in ["from", "to"]:
            if str(step.get(key)) not in participants:
                findings.append(finding("cross_repo_contract_review", "high", f"system interaction sequence step {key} is not listed as a participant", {"index": idx, key: step.get(key), "participants": participants}, "Keep participants and sequence edges consistent."))
        if normalized_text(step.get("action")) not in normalized_diagram:
            findings.append(finding("cross_repo_contract_review", "high", "system sequence diagram misses a reviewed action", {"index": idx, "action": step.get("action")}, "Keep the Mermaid sequence diagram aligned with structured interaction actions."))


def review_integration_sequence_diagram(integration_sequence: list[Any], diagram: Any, findings: list[dict[str, Any]]) -> None:
    if not integration_sequence:
        return
    text = str(diagram or "").strip()
    if not text:
        findings.append(finding("cross_repo_contract_review", "blocker", "integration sequence diagram is missing", "integration_sequence_diagram empty", "Render a Mermaid sequence diagram from the reviewed integration sequence."))
        return
    if "```mermaid" not in text.lower() or "sequencediagram" not in text.lower():
        findings.append(finding("cross_repo_contract_review", "high", "integration sequence diagram must be Mermaid sequenceDiagram", diagram, "Use Mermaid sequenceDiagram syntax for architecture-level integration flow."))
        return
    normalized_diagram = normalized_text(text)
    for idx, step in enumerate(integration_sequence):
        if not isinstance(step, dict):
            findings.append(finding("cross_repo_contract_review", "high", "integration sequence step must be an object", {"index": idx, "value": step}, "Represent architecture integration steps as structured objects."))
            continue
        missing = missing_required(step, ["step", "action", "failure_handling"])
        if not (step.get("from") or step.get("actor")):
            missing.append("from")
        if not (step.get("to") or step.get("target")):
            missing.append("to")
        if not (step.get("entrypoint") or step.get("contract")):
            missing.append("entrypoint_or_contract")
        if not step.get("data"):
            missing.append("data")
        if not step.get("owner_repo"):
            missing.append("owner_repo")
        if missing:
            findings.append(finding("cross_repo_contract_review", "high", "integration sequence step lacks required fields", {"index": idx, "missing": missing}, "Add from/to, owner_repo, entrypoint or contract, data, action, and failure_handling."))
        if normalized_text(step.get("action")) not in normalized_diagram:
            findings.append(finding("cross_repo_contract_review", "high", "integration sequence diagram misses a reviewed action", {"index": idx, "action": step.get("action")}, "Keep the Mermaid integration diagram aligned with structured integration actions."))


def review_integration_sequence_rewrite(
    integration_sequence: list[Any],
    acceptance_mapping: list[Any],
    requirement_breakdown: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> None:
    source_texts = [
        str(item.get("summary") or item.get("criteria") or item.get("design_refs") or "")
        for item in [*acceptance_mapping, *requirement_breakdown]
        if isinstance(item, dict)
    ]
    for idx, step in enumerate(integration_sequence):
        if not isinstance(step, dict):
            continue
        action = str(step.get("action") or "")
        weak_shape = not (step.get("entrypoint") and step.get("contract") and step.get("data") and step.get("owner_repo"))
        if weak_shape and any(similarity_ratio(action, source) >= 0.82 for source in source_texts):
            findings.append(finding(
                "cross_repo_contract_review",
                "high",
                "integration sequence looks like acceptance criteria rewritten as a sequence step",
                {"index": idx, "action": action},
                "Replace AC/BRK prose with an execution step that names from/to, owner repo, entrypoint/contract, data exchanged, and failure handling.",
            ))


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


def review(
    technical: dict[str, Any],
    architecture: dict[str, Any],
    ui_ue_artifact: dict[str, Any] | None = None,
    specialty_artifacts: dict[str, dict[str, Any]] | None = None,
    architecture_framing_artifact: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    specialty_artifacts = specialty_artifacts or {}
    specialty_summary = review_specialty_artifacts(specialty_artifacts, findings)
    current_state = technical.get("current_state_analysis") if isinstance(technical.get("current_state_analysis"), dict) else {}
    problem_analysis = technical.get("problem_analysis") if isinstance(technical.get("problem_analysis"), dict) else {}
    requirement_breakdown = [item for item in as_list(technical.get("requirement_breakdown")) if isinstance(item, dict)]
    entrypoint_confidence = technical.get("code_entrypoint_confidence") if isinstance(technical.get("code_entrypoint_confidence"), dict) else {}
    req_trace = as_list(technical.get("requirement_trace"))
    target_behavior = as_list(technical.get("target_behavior"))
    business_rules = as_list(technical.get("business_rule_mapping"))
    process_flow = as_list(technical.get("process_flow"))
    process_flow_diagram = technical.get("process_flow_diagram")
    modules = as_list(technical.get("module_decomposition"))
    logical_data_flow = as_list(technical.get("logical_data_flow"))
    api_contracts = as_list(technical.get("api_contracts"))
    data_design = as_list(technical.get("data_design"))
    data_model_design = technical.get("data_model_design") if isinstance(technical.get("data_model_design"), dict) else {}
    table_schema_changes = as_list(technical.get("table_schema_changes"))
    system_interaction_sequence = technical.get("system_interaction_sequence") if isinstance(technical.get("system_interaction_sequence"), dict) else {}
    system_sequence_diagram = technical.get("system_sequence_diagram")
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
    architecture_framing = (
        architecture_framing_artifact
        if isinstance(architecture_framing_artifact, dict) and architecture_framing_artifact
        else technical.get("architecture_framing")
        if isinstance(technical.get("architecture_framing"), dict)
        else architecture.get("architecture_framing")
        if isinstance(architecture.get("architecture_framing"), dict)
        else {}
    )
    applicability = {
        str(item.get("area", "")).lower(): str(item.get("status", "")).lower()
        for item in as_list(technical.get("impact_applicability"))
        if isinstance(item, dict) and item.get("area")
    }
    api_excluded = applicability.get("api") in {"excluded", "not_applicable"}
    data_excluded = applicability.get("data") in {"excluded", "not_applicable"}

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
    integration_sequence_diagram = architecture.get("integration_sequence_diagram")
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
    data_signal = not data_excluded and has_signal(design_blob, ("database", "table", "field", "schema", "migration", "数据", "字段", "表", "迁移"))
    system_signal = has_signal(design_blob, ("api", "endpoint", "service", "repo", "system", "consumer", "provider", "接口", "服务", "系统", "跨仓", "上下游"))
    mq_signal = has_signal(design_blob, ("mq", "topic", "queue", "producer", "consumer", "message", "event", "kafka", "rocketmq", "rabbitmq", "消息", "队列", "生产者", "消费者"))
    cache_signal = has_signal(design_blob, ("cache", "redis", "ttl", "缓存", "高频", "热点"))
    consistency_signal = has_signal(design_blob, ("transaction", "consistency", "idempot", "rollback", "compensation", "事务", "一致性", "幂等", "补偿", "回滚"))
    framing_signal = system_signal or data_signal or mq_signal or new_service_signal(technical, architecture)

    review_requirements_understanding_gate(technical, architecture, findings)
    review_local_project_binding(technical, architecture, findings)
    review_architecture_routing_evidence(architecture, findings)
    if framing_signal:
        if not architecture_framing and not technical.get("architecture_framing_ref") and not architecture.get("architecture_framing_ref"):
            findings.append(finding("architecture_boundary_review", "high", "complex design lacks pre-technical architecture framing", "architecture_framing.json missing", "Generate architecture_framing.json before detailed technical design for API/data/MQ/cross-system/new-service requirements."))
        elif architecture_framing.get("decision") == "block":
            findings.append(finding("architecture_boundary_review", "blocker", "pre-technical architecture framing is blocked", architecture_framing.get("blockers"), "Resolve owner repo, entrypoint, data ownership, provider/consumer, or new-service boundary blockers before implementation."))

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
    source_locations = technical.get("source_location_evidence") if isinstance(technical.get("source_location_evidence"), dict) else architecture.get("source_location_evidence") if isinstance(architecture.get("source_location_evidence"), dict) else {}
    technical_binding = technical.get("local_project_binding") if isinstance(technical.get("local_project_binding"), dict) else {}
    architecture_binding = architecture.get("local_project_binding") if isinstance(architecture.get("local_project_binding"), dict) else {}
    repository_backed_design = bool(project_context.get("repo_root") or source_locations.get("repo_root") or technical_binding or architecture_binding)
    if source_locations:
        confirmed_paths = {
            str(item.get("path")) for item in as_list(source_locations.get("confirmed_anchors"))
            if isinstance(item, dict) and item.get("path") and item.get("role", "modify_candidate") != "reference_only"
        }
        rejected_paths = {
            str(item.get("path")) for item in as_list(source_locations.get("rejected_candidates"))
            if isinstance(item, dict) and item.get("path")
        }
        if source_locations.get("decision") != "pass" or not confirmed_paths:
            findings.append(finding("technical_design_quality", "high", "requirement-specific source location evidence did not pass", source_locations, "Inspect source and confirm at least one requirement-specific entrypoint before design."))
        if selected_entrypoint and selected_entrypoint not in confirmed_paths:
            findings.append(finding("technical_design_quality", "high", "selected entrypoint is not a confirmed source anchor", selected_entrypoint, "Select an entrypoint from source_location_evidence.confirmed_anchors."))
        design_text = text_of([
            technical.get("process_flow"),
            technical.get("module_decomposition"), technical.get("logical_data_flow"), technical.get("api_contracts"),
            technical.get("system_interaction_sequence"), architecture.get("current_architecture"), architecture.get("module_topology"),
            architecture.get("integration_sequence"), technical.get("selected_solution"), architecture.get("selected_architecture"),
        ])
        leaked_rejected = sorted(path for path in rejected_paths if path and path.lower() in design_text)
        if leaked_rejected:
            findings.append(finding("technical_design_quality", "high", "rejected source candidates leaked into implementation-facing design", leaked_rejected, "Remove rejected paths from modules, selected options, rollback, and delivery scope."))
        module_paths = {
            str(item.get("module")) for item in [*as_list(technical.get("module_decomposition")), *as_list(architecture.get("module_topology"))]
            if isinstance(item, dict) and item.get("module")
        }
        unconfirmed_modules = sorted(path for path in module_paths if looks_like_path(path) and path not in confirmed_paths)
        if unconfirmed_modules:
            findings.append(finding("technical_design_quality", "high", "implementation modules are not confirmed by source location evidence", unconfirmed_modules, "Confirm each modify module directly or keep it read-only/reference-only."))
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
    review_semantic_hygiene(
        technical,
        architecture,
        api_contracts,
        data_model_design,
        repo_responsibilities,
        data_excluded,
        findings,
    )
    if not business_rules:
        findings.append(finding("technical_design_quality", "high", "business rules are not mapped to technical enforcement", "business_rule_mapping empty", "Map each business rule to API/service/query/frontend/export enforcement."))
    elif any(isinstance(item, dict) and not (item.get("technical_enforcement") and item.get("source_of_truth")) for item in business_rules):
        findings.append(finding("technical_design_quality", "high", "business rule mapping lacks enforcement or source of truth", business_rules, "Each rule needs technical_enforcement and source_of_truth."))
    review_acceptance_literal_guard(technical, architecture, findings)
    review_generic_constraints(technical, architecture, findings)

    review_process_flow(process_flow, findings)
    review_process_flow_diagram(process_flow, process_flow_diagram, findings)
    process_step_count = sum(len(as_list(item.get("steps"))) for item in process_flow if isinstance(item, dict))
    if len(as_list(technical.get("acceptance_mapping"))) >= 2 and process_step_count < 2:
        findings.append(finding("technical_design_quality", "high", "business process flow is too shallow for the mapped acceptance scope", {"process_steps": process_step_count, "acceptance_mappings": len(as_list(technical.get("acceptance_mapping")))}, "Model the ordered trigger, business actions, downstream effects, success state, and failure branches before implementation."))
    review_module_decomposition(modules, findings)
    for idx, item in enumerate(modules):
        if isinstance(item, dict) and item.get("module") and not looks_like_path(str(item.get("module"))) and item.get("planned_new_module") is not True:
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
            contract_text = str(item.get("contract") or item.get("endpoint") or "")
            if contract_text and is_external_provider_contract(contract_text):
                continue
            if contract_text and "no api impact confirmed" not in contract_text.lower() and not (item.get("source_evidence") or item.get("controller_file") or item.get("frontend_proxy_path")):
                findings.append(finding("api_contract_review", "high", "API contract lacks source binding evidence", {"index": idx, "contract": contract_text}, "Bind every concrete API contract to api_surface/source_location evidence, controller file, or frontend proxy path."))
            if contract_text and contract_text.strip() in {"/list", "/paging", "/page"} and not item.get("source_evidence"):
                findings.append(finding("api_contract_review", "high", "API contract appears guessed from a generic list/page route", {"index": idx, "contract": contract_text}, "Replace guessed generic endpoints with confirmed routes from source evidence."))
    confirmed_contracts = {
        str(contract).split(" (", 1)[0].strip()
        for contract in as_list(source_locations.get("confirmed_contracts") if isinstance(source_locations, dict) else [])
        if str(contract).strip()
    }
    if confirmed_contracts:
        for idx, item in enumerate(api_contracts):
            if not isinstance(item, dict):
                continue
            endpoint = str(item.get("endpoint") or item.get("contract") or "").split(" (", 1)[0].strip()
            if endpoint.startswith("/") and not is_external_provider_contract(endpoint) and endpoint not in confirmed_contracts:
                findings.append(finding("api_contract_review", "high", "API contract is not in confirmed source contracts", {"index": idx, "endpoint": endpoint, "confirmed_contracts": sorted(confirmed_contracts)}, "Use only confirmed_contracts from source location evidence or regenerate source evidence."))
    if api_contracts and not interface_examples and not api_excluded:
        findings.append(finding("api_contract_review", "medium", "API/interface examples are missing", "interface_examples empty", "Add request/response/error examples or an explicit no-example reason."))
    if "api" in text_of(technical) and not api_contracts:
        findings.append(finding("api_contract_review", "high", "API-related design lacks API contracts", "api term detected", "Add API contract table or explicit no API impact reason."))

    if not data_design and not data_excluded:
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
            if item.get("applicable") is False and item.get("change_type") == "none":
                continue
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
            review_system_sequence_diagram(system_interaction_sequence, system_sequence_diagram, findings)

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
        if repository_backed_design and isinstance(item, dict) and item.get("role") == "modify" and not str(item.get("repo_path") or "").strip():
            findings.append(finding("repo_responsibility_review", "blocker", "modify repo lacks concrete repo_path", {"index": idx, "repo": item.get("repo")}, "Bind every modify repo to the actual local repository path before delivery planning or implementation."))

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
    else:
        review_integration_sequence_diagram(integration_sequence, integration_sequence_diagram, findings)
        review_integration_sequence_rewrite(integration_sequence, acceptance_mapping, requirement_breakdown, findings)
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
    diagram_checks = {
        "process_flow_diagram": {
            "required": bool(process_flow),
            "present": bool(str(process_flow_diagram or "").strip()),
        },
        "system_sequence_diagram": {
            "required": bool(isinstance(system_interaction_sequence, dict) and system_interaction_sequence.get("applicable") is True),
            "present": bool(str(system_sequence_diagram or "").strip()),
        },
        "integration_sequence_diagram": {
            "required": bool(integration_sequence),
            "present": bool(str(integration_sequence_diagram or "").strip()),
        },
    }
    source_location_checks = {
        "provided": bool(source_locations),
        "decision": source_locations.get("decision", "") if isinstance(source_locations, dict) else "",
        "confirmed_modify_count": len([
            item for item in as_list(source_locations.get("confirmed_anchors") if isinstance(source_locations, dict) else [])
            if isinstance(item, dict) and item.get("role", "modify_candidate") != "reference_only"
        ]),
        "selected_entrypoint": selected_entrypoint,
        "selected_entrypoint_confirmed": bool(selected_entrypoint and source_locations and selected_entrypoint in {
            str(item.get("path")) for item in as_list(source_locations.get("confirmed_anchors"))
            if isinstance(item, dict) and item.get("path") and item.get("role", "modify_candidate") != "reference_only"
        }),
    }
    return {
        "schema": "codex-design-architecture-review-v1",
        "input_digests": {
            "technical_design.json": artifact_digest(technical),
            "architecture_design.json": artifact_digest(architecture),
            **({"architecture_framing.json": artifact_digest(architecture_framing)} if architecture_framing else {}),
            **{name: artifact_digest(data) for name, data in specialty_artifacts.items() if data},
        },
        "specialty_review_summary": specialty_summary,
        "diagram_checks": diagram_checks,
        "source_location_checks": source_location_checks,
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
    required = ["schema", "score", "level", "severity_counts", "readiness_gate", "open_questions", "solution_tradeoff_review", "blockers", "decision", "diagram_checks", "source_location_checks", *REVIEW_AREAS]
    issues = [f"missing {key}" for key in required if key not in data]
    if data.get("schema") != "codex-design-architecture-review-v1":
        issues.append("schema must be codex-design-architecture-review-v1")
    if data.get("decision") not in {"pass", "needs_revision", "block"}:
        issues.append("decision must be pass/needs_revision/block")
    if data.get("decision") == "pass" and data.get("blockers"):
        issues.append("pass is not allowed with blockers")
    if data.get("decision") == "pass":
        if not isinstance(data.get("diagram_checks"), dict) or not data["diagram_checks"]:
            issues.append("pass requires non-empty diagram_checks")
        if not isinstance(data.get("source_location_checks"), dict):
            issues.append("pass requires source_location_checks")
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
    p_review.add_argument("--architecture-framing")
    p_review.add_argument("--ui-ue-design")
    p_review.add_argument("--ui-ue-review")
    p_review.add_argument("--api-contract-design")
    p_review.add_argument("--data-model-design")
    p_review.add_argument("--observability-design")
    p_review.add_argument("--configuration-readiness")
    p_review.add_argument("--data-security-review")
    p_review.add_argument("--performance-review")
    p_review.add_argument("--cross-repo-readiness")
    p_review.add_argument("--test-design")
    p_review.add_argument("--out")
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--file", required=True)
    args = parser.parse_args()

    if args.cmd == "review":
        specialty_paths = {
            "ui_ue_review.json": args.ui_ue_review,
            "api_contract_design.json": args.api_contract_design,
            "data_model_design.json": args.data_model_design,
            "observability_design.json": args.observability_design,
            "configuration_readiness.json": args.configuration_readiness,
            "data_security_review.json": args.data_security_review,
            "performance_review.json": args.performance_review,
            "cross_repo_readiness.json": args.cross_repo_readiness,
            "test_design.json": args.test_design,
        }
        result = review(
            read_json(args.technical_design),
            read_json(args.architecture_design),
            read_json(args.ui_ue_design) if args.ui_ue_design else None,
            {name: read_json(path) for name, path in specialty_paths.items() if path},
            read_json(args.architecture_framing) if args.architecture_framing else None,
        )
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
