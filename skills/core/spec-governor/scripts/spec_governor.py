#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-spec-v1"
IMPACT_AREAS = {
    "api": ("api", "endpoint", "route", "接口", "端点"),
    "ui": ("ui", "ux", "page", "screen", "button", "frontend", "页面", "按钮", "前端"),
    "data": ("data", "database", "db", "sql", "migration", "字段", "数据库", "数据", "迁移"),
    "permission": ("permission", "role", "tenant", "admin", "operator", "auth", "权限", "角色", "租户", "管理员"),
    "config": ("config", "env", "feature flag", "配置", "环境变量", "开关"),
    "performance": ("performance", "latency", "slow", "export", "batch", "性能", "延迟", "导出", "批量"),
    "security": ("security", "pii", "secret", "payment", "安全", "隐私", "密钥", "支付"),
}
SHALLOW_TERMS = {"user", "existing source", "test evidence", "expected behavior", "preserve existing", "待确认", "unknown", "tbd"}
BUSINESS_OBJECT_TERMS = {
    "order": ("order", "orders", "订单"),
    "payment": ("payment", "payments", "支付"),
    "invoice": ("invoice", "invoices", "发票"),
    "customer": ("customer", "customers", "客户"),
    "report": ("report", "reports", "报表"),
    "export_file": ("export", "file", "csv", "excel", "导出", "文件"),
    "dashboard": ("dashboard", "page", "screen", "页面", "看板"),
}
FIELD_TERMS = {
    "id": (" id", "order id", "payment id", "编号", "id"),
    "status": ("status", "状态"),
    "retry_count": ("retry count", "retry_count", "重试次数"),
    "failure_reason": ("failure reason", "失败原因"),
    "amount": ("amount", "金额"),
    "email": ("email", "邮箱"),
    "phone": ("phone", "手机号", "电话"),
}
OPERATION_TERMS = {
    "export": ("export", "download", "导出", "下载"),
    "view": ("view", "see", "show", "open", "查看", "展示", "打开"),
    "create": ("create", "add", "新增", "创建"),
    "update": ("update", "edit", "change", "修改", "编辑"),
    "delete": ("delete", "remove", "删除"),
    "retry": ("retry", "重试"),
}
HIGH_RISK_IMPACTS = {"data", "permission", "security", "performance", "api", "config"}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def split_lines(text: str) -> list[str]:
    return [line.strip(" \t-*#") for line in text.splitlines() if line.strip(" \t-*#")]


def normalize_list_item(line: str) -> str:
    return re.sub(r"^\s*(?:[-*]\s+|\d+[.)、]\s*|[（(]\d+[）)]\s*)", "", line).strip()


def is_section_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if re.match(r"^#{1,6}\s+", stripped):
        return True
    compact = stripped.strip("# \t")
    return bool(re.match(r"^(范围|可执行需求|需求|验收标准|非范围|非目标|业务规则|背景|说明|acceptance criteria|acceptance|requirements?|scope|out of scope|business rules?)$", compact, re.I))


def section_title(line: str) -> str:
    return re.sub(r"^#{1,6}\s*", "", line).strip().strip("#").strip()


def collect_section_items(raw_text: str, headings: tuple[str, ...]) -> list[str]:
    items: list[str] = []
    in_section = False
    for raw_line in raw_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        title = section_title(stripped)
        if is_section_heading(stripped):
            normalized_title = title.lower().strip()
            in_section = any(normalized_title == heading.lower() or title == heading for heading in headings)
            continue
        if not in_section:
            continue
        if re.match(r"^\s*(?:[-*]\s+|\d+[.)、]\s*|[（(]\d+[）)]\s*)", raw_line):
            item = normalize_list_item(raw_line)
            if item:
                items.append(item)
            continue
        if items and raw_line.startswith((" ", "\t")):
            items[-1] = f"{items[-1]}；{stripped}"
    return items


def classify_lane(text: str) -> str:
    lower = text.lower()
    if any(term in lower for term in ["hotfix", "production down", "p0", "urgent"]):
        return "hotfix"
    if any(term in lower for term in ["bug", "fix", "defect", "报错", "修复"]):
        return "bugfix"
    if len(text) > 3000 or len(split_lines(text)) > 30:
        return "large_prd"
    if len(text) < 300:
        return "small_change"
    return "standard_requirement"


def extract_acceptance(lines: list[str], raw_text: str = "") -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    ac_pattern = re.compile(r"^(ac|acceptance|acceptance criteria|验收|验收标准|标准)[:：\s-]*(.+)$", re.I)
    for line in lines:
        match = ac_pattern.match(line)
        if match:
            criteria = match.group(2).strip()
            if not criteria or criteria in {"标准", "验收标准", "acceptance", "acceptance criteria"}:
                continue
            result.append({
                "id": f"AC-{len(result) + 1}",
                "criteria": criteria,
                "type": "negative" if is_negative(criteria) else "positive",
                "evidence_required": evidence_for_text(criteria),
                "source_evidence": "input",
            })
    for criteria in collect_section_items(raw_text, ("验收标准", "acceptance criteria", "acceptance")):
        if criteria and criteria not in {str(item.get("criteria")) for item in result}:
            result.append({
                "id": f"AC-{len(result) + 1}",
                "criteria": criteria,
                "type": "negative" if is_negative(criteria) else "positive",
                "evidence_required": evidence_for_text(criteria),
                "source_evidence": "input section: acceptance",
            })
    if not result and lines:
        result.append({"id": "AC-1", "criteria": f"User-visible behavior matches: {lines[0]}", "type": "positive", "evidence_required": ["test evidence"], "source_evidence": "inferred from first line"})
    return result


def extract_requirements(lines: list[str], raw_text: str = "") -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    req_pattern = re.compile(r"^(req|requirement|需求|功能)[:：\s-]*(.+)$", re.I)
    skip_pattern = re.compile(r"^(ac|acceptance|验收|验收标准|标准|rule|规则|out of scope|非目标|assumption|假设|risk|风险)[:：\s-]*", re.I)
    for idx, line in enumerate(lines, start=1):
        match = req_pattern.match(line)
        if match:
            result.append({"id": f"REQ-{len(result) + 1}", "summary": match.group(2).strip(), "source_evidence": f"input line {idx}"})
    for summary in collect_section_items(raw_text, ("可执行需求", "需求列表", "requirements", "requirement")):
        if summary and summary not in {str(item.get("summary")) for item in result}:
            result.append({"id": f"REQ-{len(result) + 1}", "summary": summary, "source_evidence": "input section: requirements"})
    if not result:
        for idx, line in enumerate(lines, start=1):
            if skip_pattern.match(line) or "?" in line or "？" in line:
                continue
            result.append({"id": f"REQ-{len(result) + 1}", "summary": line, "source_evidence": f"input line {idx}"})
            if len(result) >= 3:
                break
    return result


def extract_rules(lines: list[str]) -> list[dict[str, str]]:
    rules: list[dict[str, str]] = []
    for line in lines:
        lower = line.lower()
        if any(term in lower for term in ["must", "should", "rule", "when", "if ", "only", "can", "allow", "不能", "必须", "规则", "如果", "当", "允许", "可以"]):
            rules.append({"id": f"BR-{len(rules) + 1}", "rule": line, "source_evidence": "input"})
    return rules


def extract_open_questions(lines: list[str]) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    for line in lines:
        if "?" in line or "？" in line or any(term in line.lower() for term in ["tbd", "todo", "待确认", "不确定"]):
            questions.append({"id": f"Q-{len(questions) + 1}", "question": line, "owner": "product/engineering", "status": "open"})
    return questions


def matched_terms(text: str, vocabulary: dict[str, tuple[str, ...]]) -> dict[str, list[str]]:
    lower = text.lower()
    result: dict[str, list[str]] = {}
    for name, terms in vocabulary.items():
        hits = sorted({term for term in terms if term in lower or term in text})
        if hits:
            result[name] = hits
    return result


def extract_business_objects(text: str) -> list[dict[str, Any]]:
    objects = []
    for name, hits in matched_terms(text, BUSINESS_OBJECT_TERMS).items():
        objects.append({"name": name, "signals": hits, "source_evidence": "input"})
    return objects


def extract_data_fields(text: str, lines: list[str]) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    for name, hits in matched_terms(text, FIELD_TERMS).items():
        fields.append({"name": name, "signals": ", ".join(hits), "source_evidence": "input"})
    for line in lines:
        match = re.match(r"^(field|字段)[:：\s-]*(.+)$", line, flags=re.I)
        if match:
            field = match.group(2).strip()
            if field and field not in {item["name"] for item in fields}:
                fields.append({"name": field, "signals": "explicit field line", "source_evidence": "input"})
    return fields


def extract_operations(text: str) -> list[dict[str, Any]]:
    return [{"name": name, "signals": hits, "source_evidence": "input"} for name, hits in matched_terms(text, OPERATION_TERMS).items()]


def extract_state_transitions(lines: list[str]) -> list[dict[str, str]]:
    transitions: list[dict[str, str]] = []
    patterns = [
        re.compile(r"from\s+(.+?)\s+to\s+(.+)", re.I),
        re.compile(r"状态\s*从\s*(.+?)\s*(?:到|变为)\s*(.+)"),
    ]
    for line in lines:
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                transitions.append({"from": match.group(1).strip(), "to": match.group(2).strip(), "source_evidence": line})
                break
    return transitions


def rule_action(rule: str) -> str:
    lower = rule.lower()
    for operation, terms in OPERATION_TERMS.items():
        if any(term in lower or term in rule for term in terms):
            return operation
    return ""


def rule_roles(rule: str) -> set[str]:
    lower = rule.lower()
    roles = set()
    if "non-admin" in lower or "非管理员" in rule:
        roles.add("non-admin")
    for role in ["admin", "operator", "customer", "user", "buyer", "管理员", "运营", "客户", "用户"]:
        if role in lower or role in rule:
            roles.add(role)
    if "non-admin" in roles and "admin" in roles:
        roles.remove("admin")
    return roles


def is_allow_rule(rule: str) -> bool:
    lower = rule.lower()
    if any(term in lower for term in ["cannot", "must not", "should not", "unauthorized", "deny", "forbid"]) or any(term in rule for term in ["不能", "不得", "禁止", "无权限"]):
        return False
    return bool(re.search(r"\b(can|allow|allows|allowed)\b", lower)) or any(term in rule for term in ["允许", "可以"])


def detect_rule_conflicts(rules: list[dict[str, str]]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    normalized = [{"id": item.get("id", ""), "rule": item.get("rule", ""), "action": rule_action(item.get("rule", "")), "roles": rule_roles(item.get("rule", ""))} for item in rules]
    for first in normalized:
        lower = first["rule"].lower()
        if "only admin" not in lower and "仅管理员" not in first["rule"] and "只有管理员" not in first["rule"]:
            continue
        for second in normalized:
            if first is second or not first["action"] or first["action"] != second["action"]:
                continue
            if second["roles"] - {"admin", "管理员"} and is_allow_rule(second["rule"]):
                conflicts.append({
                    "id": f"CONFLICT-{len(conflicts) + 1}",
                    "type": "permission_rule_conflict",
                    "rules": [first["id"], second["id"]],
                    "message": f"{first['rule']} conflicts with {second['rule']}",
                    "severity": "blocker",
                })
    return conflicts


def infer_implicit_constraints(impacts: list[dict[str, Any]], objects: list[dict[str, Any]], fields: list[dict[str, str]]) -> list[dict[str, str]]:
    areas = {str(item.get("area")) for item in impacts if isinstance(item, dict)}
    object_names = {str(item.get("name")) for item in objects if isinstance(item, dict)}
    field_names = {str(item.get("name")) for item in fields if isinstance(item, dict)}
    constraints: list[dict[str, str]] = []

    def add(area: str, constraint: str, question: str, required: bool = True) -> None:
        constraints.append({"area": area, "constraint": constraint, "question": question, "status": "requires_confirmation" if required else "advisory"})

    if "permission" in areas:
        add("permission", "Role/data-scope boundary must be explicit", "Which roles can perform the operation, and which negative permission cases must pass?")
    if "data" in areas or "export_file" in object_names:
        add("data", "Data fields and business definitions must be explicit", "Which fields, filters, data definitions, and masking rules are required?")
    if "security" in areas or {"email", "phone", "amount"} & field_names:
        add("security", "Sensitive fields need access, masking, and audit requirements", "Which sensitive fields require masking, audit logging, or restricted access?")
    if "api" in areas:
        add("api", "API compatibility and error behavior must be explicit", "Which endpoint, request/response fields, error codes, and old-consumer compatibility rules apply?")
    if "performance" in areas:
        add("performance", "Performance threshold and data scale must be explicit", "What latency, throughput, export size, and test data volume thresholds must be met?")
    if "config" in areas:
        add("config", "Configuration default, rollout, and rollback behavior must be explicit", "What are the default values, rollout scope, and rollback behavior for configuration changes?")
    return constraints


def constraint_questions(constraints: list[dict[str, str]], existing_questions: list[dict[str, str]]) -> list[dict[str, str]]:
    existing = {str(item.get("question") or "").strip() for item in existing_questions if isinstance(item, dict)}
    questions: list[dict[str, str]] = []
    for item in constraints:
        question = str(item.get("question") or "").strip()
        if not question or question in existing:
            continue
        questions.append({
            "id": f"CQ-{len(questions) + 1}",
            "area": str(item.get("area") or ""),
            "question": question,
            "owner": "product/engineering",
            "status": "derived",
            "source": "implicit_constraints",
        })
    return questions


def expert_readiness_gaps(
    impact_surface: list[dict[str, Any]],
    acceptance: list[dict[str, Any]],
    objectives: list[dict[str, str]],
    scenarios: list[dict[str, Any]],
    risks: list[dict[str, str]],
    compatibility: list[str],
) -> list[dict[str, str]]:
    areas = {str(item.get("area")) for item in impact_surface if isinstance(item, dict)}
    gaps: list[dict[str, str]] = []

    def add(source: str, message: str, severity: str = "medium") -> None:
        gaps.append({"source": source, "message": message, "severity": severity})

    if not objectives:
        add("business_objectives", "Business objective is missing; design may optimize the wrong outcome.")
    if not scenarios:
        add("user_scenarios", "User scenario is missing; acceptance may not cover the real workflow.")
    if acceptance and all(not str(item.get("source_evidence")).startswith("input") for item in acceptance):
        add("acceptance_criteria", "Acceptance is inferred rather than explicitly provided.", "high")
    if areas & {"api", "data", "permission", "security", "performance", "config"} and not risks:
        add("risks", "High-impact requirement should declare explicit delivery or product risks.", "high")
    if "api" in areas and not compatibility:
        add("compatibility_constraints", "API impact should state backward compatibility or consumer migration constraints.", "high")
    return gaps


def is_negative(text: str) -> bool:
    lower = text.lower()
    return any(token in lower for token in ["cannot", "must not", "should not", "deny", "forbid", "unauthorized", "non-admin", "不能", "不得", "禁止", "无权限", "非管理员"])


def evidence_for_text(text: str) -> list[str]:
    lower = text.lower()
    evidence = ["functional_test"]
    if any(token in lower for token in ["ui", "page", "button", "screen", "页面", "按钮", "前端"]):
        evidence.append("frontend_acceptance")
    if any(token in lower for token in ["api", "endpoint", "接口"]):
        evidence.append("api_test")
    if any(token in lower for token in ["permission", "role", "admin", "unauthorized", "权限", "角色", "管理员", "无权限"]):
        evidence.append("permission_negative_test")
    if any(token in lower for token in ["export", "file", "csv", "excel", "导出", "文件"]):
        evidence.append("export_evidence")
    return sorted(set(evidence))


def detect_impact_surface(text: str) -> list[dict[str, Any]]:
    lower = text.lower()
    result: list[dict[str, Any]] = []
    for area, terms in IMPACT_AREAS.items():
        matched = [term for term in terms if term in lower or term in text]
        if matched:
            result.append({"area": area, "signals": sorted(set(matched)), "status": "detected"})
    return result


def extract_personas(actors: list[str]) -> list[dict[str, str]]:
    return [{"actor": actor, "goal": "complete requirement outcome", "permission_boundary": "confirm in design"} for actor in actors]


def extract_user_scenarios(lines: list[str], actors: list[str]) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    pattern = re.compile(r"^(scenario|场景)[:：\s-]*(.+)$", re.I)
    for line in lines:
        match = pattern.match(line)
        if match:
            scenarios.append({"id": f"SC-{len(scenarios) + 1}", "actor": actors[0], "trigger": match.group(2).strip(), "preconditions": [], "expected_outcome": match.group(2).strip(), "source_evidence": "input"})
    if not scenarios and lines:
        scenarios.append({"id": "SC-1", "actor": actors[0], "trigger": lines[0], "preconditions": [], "expected_outcome": lines[0], "source_evidence": "inferred from first line"})
    return scenarios


def extract_business_objectives(lines: list[str]) -> list[dict[str, str]]:
    objectives = extract_prefixed(lines, ("objective", "goal", "业务目标", "目标"))
    if objectives:
        return [{"id": f"BO-{idx + 1}", "objective": item, "source_evidence": "input"} for idx, item in enumerate(objectives)]
    return []


def classify_data(text: str) -> dict[str, Any]:
    lower = text.lower()
    signals = []
    if any(token in lower for token in ["email", "phone", "address", "name", "pii", "手机号", "邮箱", "姓名", "地址"]):
        signals.append("personal_data")
    if any(token in lower for token in ["payment", "card", "invoice", "支付", "银行卡", "发票"]):
        signals.append("payment_or_financial")
    return {"classification": "sensitive" if signals else "unknown", "signals": signals, "requires_security_review": bool(signals)}


def extract_prefixed(lines: list[str], prefixes: tuple[str, ...]) -> list[str]:
    pattern = re.compile(rf"^({'|'.join(re.escape(item) for item in prefixes)})[:：\s-]*(.+)$", re.I)
    result: list[str] = []
    for line in lines:
        match = pattern.match(line)
        if match:
            result.append(match.group(2).strip())
    return result


def normalize(doc_id: str, title: str, text: str) -> dict[str, Any]:
    lines = split_lines(text)
    summary = lines[0] if lines else title
    lane = classify_lane(text)
    acceptance = extract_acceptance(lines, text)
    rules = extract_rules(lines)
    questions = extract_open_questions(lines)
    requirements = extract_requirements(lines, text)
    out_of_scope = extract_prefixed(lines, ("out of scope", "非目标", "不包含"))
    assumptions = extract_prefixed(lines, ("assumption", "假设"))
    risks = [{"id": f"RISK-{idx + 1}", "risk": item, "source_evidence": "input"} for idx, item in enumerate(extract_prefixed(lines, ("risk", "风险")))]
    non_goals = extract_prefixed(lines, ("non-goal", "non goal", "非目标"))
    actors = []
    lower = text.lower()
    for candidate in ["admin", "operator", "customer", "user", "buyer", "管理员", "用户", "客户", "运营"]:
        if candidate in lower or candidate in text:
            actors.append(candidate)
    if not actors:
        actors = ["user"]
    impact_surface = detect_impact_surface(text)
    business_objects = extract_business_objects(text)
    data_fields = extract_data_fields(text, lines)
    operations = extract_operations(text)
    state_transitions = extract_state_transitions(lines)
    personas = extract_personas(sorted(set(actors)))
    scenarios = extract_user_scenarios(lines, sorted(set(actors)))
    objectives = extract_business_objectives(lines)
    negative_acceptance = [item for item in acceptance if item.get("type") == "negative"]
    rule_conflicts = detect_rule_conflicts(rules)
    implicit_constraints = infer_implicit_constraints(impact_surface, business_objects, data_fields)
    compatibility_constraints = extract_prefixed(lines, ("compatibility", "兼容", "backward compatible", "向后兼容"))
    derived_constraint_questions = constraint_questions(implicit_constraints, questions)
    readiness_gaps = expert_readiness_gaps(impact_surface, acceptance, objectives, scenarios, risks, compatibility_constraints)
    return {
        "schema": SCHEMA,
        "doc_id": doc_id,
        "title": title,
        "lane": lane,
        "requirement_summary": summary,
        "source": {"type": "text", "line_count": len(lines)},
        "actors": sorted(set(actors)),
        "scope": {
            "in_scope": [summary] if summary else [],
            "out_of_scope": out_of_scope,
            "assumptions": assumptions,
            "non_goals": non_goals,
        },
        "requirements": requirements,
        "personas": personas,
        "user_scenarios": scenarios,
        "business_objectives": objectives,
        "business_objects": business_objects,
        "operations": operations,
        "data_fields": data_fields,
        "state_transitions": state_transitions,
        "impact_surface": impact_surface,
        "data_classification": classify_data(text),
        "permission_scope": {
            "actors": sorted(set(actors)),
            "sensitive": any(item.get("area") == "permission" for item in impact_surface),
            "negative_cases_required": any(item.get("area") == "permission" for item in impact_surface),
        },
        "compatibility_constraints": compatibility_constraints,
        "business_rules": rules,
        "rule_conflicts": rule_conflicts,
        "implicit_constraints": implicit_constraints,
        "derived_constraint_questions": derived_constraint_questions,
        "expert_readiness_gaps": readiness_gaps,
        "acceptance_criteria": acceptance,
        "negative_acceptance_criteria": negative_acceptance,
        "risks": risks,
        "open_questions": questions,
        "source_trace": [{"line": idx, "text": line} for idx, line in enumerate(lines, start=1)],
        "decision": "blocked" if questions or rule_conflicts else "ready_for_design",
        "next_action": "Resolve open questions and rule conflicts before design." if questions or rule_conflicts else "Proceed to technical and architecture design.",
    }


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if spec.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    for key in ["doc_id", "title", "requirement_summary", "lane"]:
        if not spec.get(key):
            blockers.append({"source": key, "message": f"{key} is required"})
    if not as_list(spec.get("actors")):
        blockers.append({"source": "actors", "message": "actors are required"})
    if not as_list(spec.get("requirements")):
        blockers.append({"source": "requirements", "message": "at least one requirement is required"})
    if not as_list(spec.get("acceptance_criteria")):
        blockers.append({"source": "acceptance_criteria", "message": "acceptance criteria are required"})
    scope = spec.get("scope") if isinstance(spec.get("scope"), dict) else {}
    if not as_list(scope.get("in_scope")):
        blockers.append({"source": "scope.in_scope", "message": "in_scope is required"})
    open_questions = [q for q in as_list(spec.get("open_questions")) if isinstance(q, dict) and q.get("status", "open") != "closed"]
    if open_questions:
        blockers.append({"source": "open_questions", "message": "open questions must be closed before implementation", "count": len(open_questions)})
    rule_conflicts = [item for item in as_list(spec.get("rule_conflicts")) if isinstance(item, dict)]
    if rule_conflicts:
        blockers.append({"source": "rule_conflicts", "message": "rule conflicts must be resolved before design", "count": len(rule_conflicts)})
    if not as_list(spec.get("business_rules")):
        warnings.append({"source": "business_rules", "message": "no explicit business rules were extracted"})
    if not as_list(spec.get("user_scenarios")):
        warnings.append({"source": "user_scenarios", "message": "no user scenarios were captured"})
    if not as_list(spec.get("business_objectives")):
        warnings.append({"source": "business_objectives", "message": "no business objective was captured"})
    impact_surface = [item for item in as_list(spec.get("impact_surface")) if isinstance(item, dict)]
    impact_areas = {str(item.get("area")) for item in impact_surface}
    if not impact_surface:
        warnings.append({"source": "impact_surface", "message": "no API/UI/data/permission/config/performance/security impact was detected or declared"})
    if impact_areas & HIGH_RISK_IMPACTS and not as_list(spec.get("implicit_constraints")):
        warnings.append({"source": "implicit_constraints", "message": "high-risk impacts should produce implicit constraints and clarifying questions"})
    derived_questions = [item for item in as_list(spec.get("derived_constraint_questions")) if isinstance(item, dict)]
    if impact_areas & HIGH_RISK_IMPACTS and not derived_questions:
        warnings.append({"source": "derived_constraint_questions", "message": "high-risk impacts should expose derived clarification questions"})
    readiness_gaps = [item for item in as_list(spec.get("expert_readiness_gaps")) if isinstance(item, dict)]
    high_readiness_gaps = [item for item in readiness_gaps if item.get("severity") == "high"]
    if high_readiness_gaps:
        warnings.append({"source": "expert_readiness_gaps", "message": "expert readiness gaps remain", "count": len(high_readiness_gaps)})
    permission_scope = spec.get("permission_scope") if isinstance(spec.get("permission_scope"), dict) else {}
    if permission_scope.get("negative_cases_required") and not as_list(spec.get("negative_acceptance_criteria")):
        blockers.append({"source": "negative_acceptance_criteria", "message": "permission-sensitive requirements need negative acceptance criteria"})
    data_classification = spec.get("data_classification") if isinstance(spec.get("data_classification"), dict) else {}
    if data_classification.get("requires_security_review") and not any(item.get("area") == "security" for item in impact_surface):
        warnings.append({"source": "data_classification", "message": "sensitive data detected without explicit security impact"})
    shallow_hits = []
    for key in ["requirement_summary", "actors"]:
        text = json.dumps(spec.get(key), ensure_ascii=False).lower()
        shallow_hits.extend(sorted(term for term in SHALLOW_TERMS if term in text))
    if shallow_hits:
        warnings.append({"source": "quality", "message": "spec contains shallow or placeholder language", "terms": sorted(set(shallow_hits))})
    acceptance = [item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]
    if acceptance and all(not str(item.get("source_evidence")).startswith("input") for item in acceptance):
        warnings.append({"source": "acceptance_criteria", "message": "all acceptance criteria are inferred; confirm testable acceptance before expert-ready design"})
    decision = "block" if blockers else "pass"
    return {
        "schema": "codex-spec-validation-v1",
        "decision": decision,
        "quality_level": "expert_ready" if not blockers and len(warnings) <= 1 else "usable" if not blockers else "blocked",
        "blockers": blockers,
        "warnings": warnings,
        "next_action": "Fix spec blockers before design/implementation." if blockers else "Spec is ready for design.",
    }


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize and validate requirement specs")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_norm = sub.add_parser("normalize")
    p_norm.add_argument("--doc-id", required=True)
    p_norm.add_argument("--title", required=True)
    p_norm.add_argument("--input", required=True)
    p_norm.add_argument("--out", required=True)
    p_val = sub.add_parser("validate")
    p_val.add_argument("--file", required=True)
    p_val.add_argument("--out")
    args = parser.parse_args()

    if args.cmd == "normalize":
        result = normalize(args.doc_id, args.title, read_text(Path(args.input)))
        write_json(Path(args.out), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["decision"] != "blocked" else 1
    result = validate_spec(load_json(Path(args.file)))
    if args.out:
        write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
