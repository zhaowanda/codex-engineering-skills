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
AMBIGUOUS_TERMS = {
    "优化": "ambiguous_action",
    "支持": "ambiguous_action",
    "处理": "ambiguous_action",
    "完善": "ambiguous_action",
    "同步": "ambiguous_flow",
    "修复": "ambiguous_defect",
    "调整": "ambiguous_action",
    "相关": "ambiguous_scope",
    "部分": "ambiguous_scope",
    "尽量": "ambiguous_quality",
    "默认": "ambiguous_rule",
    "按规则": "ambiguous_rule",
    "异常情况": "ambiguous_exception",
    "状态更新": "ambiguous_state",
    "自动处理": "ambiguous_action",
    "自动": "ambiguous_rule",
    "不正确": "ambiguous_defect",
    "有问题": "ambiguous_defect",
    "异常": "ambiguous_exception",
    "optimize": "ambiguous_action",
    "support": "ambiguous_action",
    "handle": "ambiguous_action",
    "improve": "ambiguous_action",
    "sync": "ambiguous_flow",
    "fix": "ambiguous_defect",
    "adjust": "ambiguous_action",
    "related": "ambiguous_scope",
    "default": "ambiguous_rule",
}
WEAK_ACCEPTANCE_TERMS = {
    "功能正常",
    "页面展示正确",
    "数据同步成功",
    "状态更新正确",
    "满足业务需求",
    "正常",
    "正确",
    "success",
    "works",
    "as expected",
}
EMPTY_ENUM_PATTERNS = [
    re.compile(r"(至少包括|include at least)[:：]\s*$", re.I),
]


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def split_lines(text: str) -> list[str]:
    return [normalize_requirement_text(line.strip(" \t-*#")) for line in text.splitlines() if line.strip(" \t-*#")]


def normalize_list_item(line: str) -> str:
    return re.sub(r"^\s*(?:[-*]\s+|\d+[.)、]\s*|[（(]\d+[）)]\s*)", "", line).strip()


def normalize_requirement_text(value: str) -> str:
    text = str(value or "").strip()
    for pattern in EMPTY_ENUM_PATTERNS:
        if pattern.search(text):
            if "至少包括" in text:
                text = pattern.sub(r"\1待确认的具体选项", text)
            else:
                text = pattern.sub(r"\1 concrete options to be confirmed", text)
    return text


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
            criteria = normalize_requirement_text(criteria)
            result.append({
                "id": f"AC-{len(result) + 1}",
                "criteria": criteria,
                "type": "negative" if is_negative(criteria) else "positive",
                "evidence_required": evidence_for_text(criteria),
                "source_evidence": "input",
            })
    for criteria in collect_section_items(raw_text, ("验收标准", "acceptance criteria", "acceptance")):
        if criteria and criteria not in {str(item.get("criteria")) for item in result}:
            criteria = normalize_requirement_text(criteria)
            result.append({
                "id": f"AC-{len(result) + 1}",
                "criteria": criteria,
                "type": "negative" if is_negative(criteria) else "positive",
                "evidence_required": evidence_for_text(criteria),
                "source_evidence": "input section: acceptance",
            })
    if not result and lines:
        result.append({"id": "AC-1", "criteria": normalize_requirement_text(lines[0]), "type": "positive", "evidence_required": ["test evidence"], "source_evidence": "inferred from first line"})
    return result


def extract_requirements(lines: list[str], raw_text: str = "") -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    req_pattern = re.compile(r"^(req|requirement|需求|功能)[:：\s-]*(.+)$", re.I)
    skip_pattern = re.compile(r"^(ac|acceptance|验收|验收标准|标准|rule|规则|out of scope|非目标|assumption|假设|risk|风险)[:：\s-]*", re.I)
    for idx, line in enumerate(lines, start=1):
        match = req_pattern.match(line)
        if match:
            result.append({"id": f"REQ-{len(result) + 1}", "summary": normalize_requirement_text(match.group(2)), "source_evidence": f"input line {idx}"})
    for summary in collect_section_items(raw_text, ("可执行需求", "需求列表", "requirements", "requirement")):
        if summary and summary not in {str(item.get("summary")) for item in result}:
            result.append({"id": f"REQ-{len(result) + 1}", "summary": normalize_requirement_text(summary), "source_evidence": "input section: requirements"})
    if not result:
        for idx, line in enumerate(lines, start=1):
            if skip_pattern.match(line) or "?" in line or "？" in line:
                continue
            result.append({"id": f"REQ-{len(result) + 1}", "summary": normalize_requirement_text(line), "source_evidence": f"input line {idx}"})
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


def extract_success_metrics(lines: list[str]) -> list[dict[str, str]]:
    metrics = extract_prefixed(lines, ("metric", "metrics", "success metric", "success criteria", "成功指标", "目标指标", "成功标准", "衡量指标"))
    return [{"id": f"METRIC-{idx + 1}", "metric": item, "source_evidence": "input"} for idx, item in enumerate(metrics)]


def explicit_business_intent(lines: list[str]) -> list[dict[str, str]]:
    intents = extract_prefixed(lines, ("business intent", "business purpose", "purpose", "why", "业务目的", "真实目的", "业务问题", "解决"))
    return [{"id": f"BI-{idx + 1}", "intent": item, "source_evidence": "input"} for idx, item in enumerate(intents)]


def infer_business_intent(summary: str, objectives: list[dict[str, str]], requirements: list[dict[str, str]], operations: list[dict[str, Any]], objects: list[dict[str, Any]]) -> dict[str, Any]:
    if objectives:
        return {
            "intent": str(objectives[0].get("objective") or ""),
            "source_evidence": objectives[0].get("source_evidence", "input"),
            "confidence": "high",
            "inference": "explicit_objective",
        }
    operation_names = [str(item.get("name")) for item in operations if isinstance(item, dict)]
    object_names = [str(item.get("name")) for item in objects if isinstance(item, dict)]
    if operation_names or object_names or requirements:
        return {
            "intent": f"Deliver the requested business outcome: {summary}",
            "source_evidence": "inferred from requirement text",
            "confidence": "medium",
            "inference": "inferred_from_action_object",
        }
    return {"intent": "", "source_evidence": "", "confidence": "low", "inference": "missing"}


def fact_assumption_split(
    intent: dict[str, Any],
    business_flow: list[dict[str, Any]],
    entrypoints: list[dict[str, str]],
    acceptance: list[dict[str, Any]],
    assumptions: list[str],
) -> dict[str, Any]:
    confirmed: list[dict[str, Any]] = []
    inferred: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    def add_fact(kind: str, value: Any, evidence: str, confidence: str) -> None:
        row = {"kind": kind, "value": value, "source_evidence": evidence, "confidence": confidence}
        if evidence == "input" and confidence == "high":
            confirmed.append(row)
        elif value not in (None, "", [], {}):
            inferred.append(row)
        else:
            unresolved.append(row)

    add_fact("business_intent", intent.get("intent"), str(intent.get("source_evidence") or ""), str(intent.get("confidence") or "low"))
    for item in business_flow:
        if isinstance(item, dict):
            add_fact("business_flow", item, str(item.get("source_evidence") or ""), str(item.get("confidence") or "low"))
    for item in entrypoints:
        if isinstance(item, dict):
            add_fact("entrypoint", item, str(item.get("source_evidence") or ""), str(item.get("confidence") or "low"))
    for item in acceptance:
        if isinstance(item, dict):
            add_fact("acceptance", item.get("criteria"), str(item.get("source_evidence") or ""), "high" if str(item.get("source_evidence") or "").startswith("input") else "medium")
    for item in assumptions:
        inferred.append({"kind": "assumption", "value": item, "source_evidence": "input", "confidence": "requires_confirmation"})
    return {"confirmed_facts": confirmed, "inferred_assumptions": inferred, "unresolved_points": unresolved}


def flow_quality_issues(business_flow: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    result_only_terms = ("状态更新正确", "数据同步成功", "功能正常", "展示正确", "处理完成", "success", "works", "as expected")
    process_terms = ("点击", "调用", "触发", "进入", "提交", "消费", "接收", "执行", "定时", "回调", "刷新", "返回", "生成", "导出", "click", "call", "trigger", "submit", "consume", "execute", "refresh", "return", "export")
    for idx, item in enumerate(business_flow):
        if not isinstance(item, dict):
            continue
        trigger = str(item.get("trigger") or "")
        behavior = str(item.get("system_behavior") or "")
        outcome = str(item.get("expected_outcome") or "")
        combined = f"{trigger} {behavior} {outcome}".lower()
        if item.get("confidence") != "high":
            issues.append({"source": f"business_flow[{idx}]", "category": "business_flow", "message": "Business flow is inferred; actor, trigger, behavior, and result must be confirmed."})
        if trigger == behavior == outcome and not any(term in combined for term in process_terms):
            issues.append({"source": f"business_flow[{idx}]", "category": "ambiguous_flow", "message": "Business flow repeats one sentence instead of separating trigger, system behavior, and outcome."})
        if any(term.lower() in combined for term in result_only_terms):
            issues.append({"source": f"business_flow[{idx}]", "category": "ambiguous_flow", "message": "Business flow describes only a desired result, not the actual business process."})
    return issues


def detect_flow_branches(text: str) -> list[dict[str, str]]:
    lower = text.lower()
    branches: list[dict[str, str]] = []
    branch_terms = {
        "success": ("成功", "正常", "success", "succeed"),
        "failure": ("失败", "异常", "报错", "failure", "failed", "error"),
        "permission_denied": ("无权限", "未授权", "unauthorized", "permission denied"),
        "retry": ("重试", "retry"),
        "timeout": ("超时", "timeout"),
        "idempotency": ("幂等", "重复请求", "duplicate", "idempotent"),
        "compensation": ("补偿", "回滚", "rollback", "compensat"),
    }
    for name, terms in branch_terms.items():
        hits = sorted({term for term in terms if term in lower or term in text})
        if hits:
            branches.append({"type": name, "signals": ", ".join(hits), "source_evidence": "input"})
    return branches


def structured_flow_step(flow_text: str, actor: str, entrypoint: str, step: int) -> dict[str, Any]:
    fragments = [part.strip(" ，,；;。.") for part in re.split(r"[，,；;。]", flow_text) if part.strip(" ，,；;。.")]
    action_terms = ("点击", "调用", "触发", "进入", "提交", "消费", "接收", "执行", "定时", "回调", "刷新", "返回", "生成", "导出", "发送", "写入", "读取", "click", "call", "trigger", "submit", "consume", "execute", "refresh", "return", "export", "send", "write", "read")
    downstream_terms = ("调用", "发送", "消费", "订阅", "mq", "topic", "queue", "接口", "api", "服务", "service", "consumer")
    system_actions = [part for part in fragments if any(term in part.lower() or term in part for term in action_terms)]
    downstream_effects = [part for part in fragments if any(term in part.lower() or term in part for term in downstream_terms)]
    return {
        "step": step,
        "actor": actor,
        "entrypoint": entrypoint,
        "trigger": fragments[0] if fragments else flow_text,
        "preconditions": [],
        "system_actions": system_actions or ([flow_text] if flow_text else []),
        "downstream_effects": downstream_effects,
        "result": fragments[-1] if fragments else flow_text,
    }


def extract_entrypoints(text: str, lines: list[str], impact_surface: list[dict[str, Any]]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    lower = text.lower()

    def add(kind: str, trigger: str, evidence: str, confidence: str = "medium") -> None:
        key = (kind, trigger)
        if key in {(item["type"], item["trigger"]) for item in entries}:
            return
        entries.append({"type": kind, "trigger": trigger, "source_evidence": evidence, "confidence": confidence})

    for line in lines:
        match = re.match(r"^(entry|入口|触发|trigger)[:：\s-]*(.+)$", line, flags=re.I)
        if match:
            add("explicit", match.group(2).strip(), "input", "high")
        scenario = re.match(r"^(scenario|场景)[:：\s-]*(.+)$", line, flags=re.I)
        if scenario:
            add("scenario_entrypoint", scenario.group(2).strip(), "input", "high")
    if any(term in lower or term in text for term in ["页面", "按钮", "菜单", "page", "button", "menu", "frontend"]):
        add("frontend_operation", "user triggers UI operation", "inferred from UI terms")
    if any(term in lower or term in text for term in ["api", "接口", "endpoint", "route"]):
        add("backend_api", "caller invokes API endpoint", "inferred from API terms")
    if any(term in lower or term in text for term in ["mq", "consumer", "topic", "queue", "消息", "消费", "订阅"]):
        add("mq_consumer", "consumer receives message", "inferred from MQ terms")
    if any(term in lower or term in text for term in ["定时", "cron", "scheduled", "scheduler", "job"]):
        add("scheduled_job", "scheduled task fires", "inferred from schedule terms")
    if any(term in lower or term in text for term in ["手工", "手动", "task", "manual"]):
        add("manual_task", "operator runs task manually", "inferred from manual task terms")
    if not entries and impact_surface:
        add("business_operation", "actor performs requested operation", "inferred from requirement impact", "low")
    return entries


def extract_business_flow(lines: list[str], actors: list[str], entrypoints: list[dict[str, str]], acceptance: list[dict[str, Any]], summary: str) -> list[dict[str, Any]]:
    flow_items = extract_prefixed(lines, ("business flow", "flow", "流程", "业务流程", "scenario", "场景"))
    if flow_items:
        result = []
        for idx, item in enumerate(flow_items):
            actor = actors[0] if actors else "actor to confirm"
            entrypoint = entrypoints[0].get("trigger", item) if entrypoints else item
            result.append({
                "step": idx + 1,
                "actor": actor,
                "trigger": item,
                "system_behavior": item,
                "expected_outcome": item,
                "structured_step": structured_flow_step(item, actor, entrypoint, idx + 1),
                "branches": detect_flow_branches(item),
                "source_evidence": "input",
                "confidence": "high",
            })
        return result
    if entrypoints and acceptance:
        actor = actors[0] if actors else "actor to confirm"
        trigger = entrypoints[0].get("trigger", "actor performs requested operation")
        return [{
            "step": 1,
            "actor": actor,
            "trigger": trigger,
            "system_behavior": summary,
            "expected_outcome": str(acceptance[0].get("criteria") or summary),
            "structured_step": structured_flow_step(f"{trigger} {summary} {acceptance[0].get('criteria') or summary}", actor, trigger, 1),
            "branches": detect_flow_branches(str(acceptance[0].get("criteria") or "")),
            "source_evidence": "inferred from entrypoint and acceptance",
            "confidence": "medium",
        }]
    return []


def extract_current_business_state(text: str, lines: list[str], entrypoints: list[dict[str, str]], impact_surface: list[dict[str, Any]]) -> dict[str, Any]:
    current_items = extract_prefixed(lines, ("current", "current state", "as is", "现状", "当前", "已有能力", "已有入口", "已有接口", "已有任务", "已有consumer", "已有消费者"))
    lower = text.lower()
    change_type = "unknown"
    if any(term in lower or term in text for term in ["复用", "reuse", "existing"]):
        change_type = "reuse_existing"
    if any(term in lower or term in text for term in ["改造", "调整", "优化", "modify", "change", "enhance"]):
        change_type = "modify_existing"
    if any(term in lower or term in text for term in ["新增", "新建", "add", "create", "new "]):
        change_type = "new_capability"
    evidence_gaps: list[dict[str, str]] = []
    if not current_items and impact_surface:
        evidence_gaps.append({
            "source": "current_business_state",
            "message": "Current entrypoints, APIs, jobs, consumers, data ownership, or downstream dependencies were not explicitly described.",
            "severity": "medium",
        })
    return {
        "summary": current_items[0] if current_items else "",
        "known_current_facts": [{"id": f"CUR-{idx + 1}", "fact": item, "source_evidence": "input"} for idx, item in enumerate(current_items)],
        "existing_entrypoints": [item for item in entrypoints if isinstance(item, dict) and item.get("confidence") == "high"],
        "change_type": change_type,
        "evidence_gaps": evidence_gaps,
    }


def weak_acceptance_reason(criteria: str) -> str:
    compact = re.sub(r"\s+", "", criteria.lower())
    if not criteria.strip():
        return "empty acceptance"
    if any(term in criteria or term in criteria.lower() or term in compact for term in WEAK_ACCEPTANCE_TERMS):
        return "acceptance is too generic to execute"
    if len(criteria.strip()) <= 4:
        return "acceptance is too short to execute"
    return ""


def ambiguous_term_context_resolved(
    term: str,
    category: str,
    acceptance: list[dict[str, Any]],
    intent: dict[str, Any],
    business_flow: list[dict[str, Any]],
    entrypoints: list[dict[str, str]],
) -> bool:
    if category in {"ambiguous_scope", "ambiguous_rule"}:
        return False
    has_intent = intent.get("confidence") == "high"
    has_entrypoint = any(item.get("confidence") == "high" for item in entrypoints if isinstance(item, dict))
    has_flow = bool(business_flow) and all(item.get("confidence") == "high" for item in business_flow if isinstance(item, dict))
    executable_acceptance = any(
        isinstance(item, dict) and not weak_acceptance_reason(str(item.get("criteria") or ""))
        for item in acceptance
    )
    branch_context = any(
        item.get("branches")
        for item in business_flow
        if isinstance(item, dict)
    )
    if category in {"ambiguous_action", "ambiguous_defect", "ambiguous_exception", "ambiguous_flow", "ambiguous_state"}:
        return bool(has_intent and has_entrypoint and has_flow and executable_acceptance and (branch_context or category != "ambiguous_exception"))
    return False


def detect_ambiguities(
    text: str,
    acceptance: list[dict[str, Any]],
    intent: dict[str, Any],
    business_flow: list[dict[str, Any]],
    entrypoints: list[dict[str, str]],
    state_transitions: list[dict[str, str]],
) -> list[dict[str, str]]:
    lower = text.lower()
    ambiguities: list[dict[str, str]] = []

    def add(source: str, category: str, message: str, required: bool = True) -> None:
        ambiguities.append({
            "id": f"AMB-{len(ambiguities) + 1}",
            "source": source,
            "category": category,
            "message": message,
            "required": required,
        })

    for term, category in AMBIGUOUS_TERMS.items():
        if term.lower() in lower or term in text:
            required = not ambiguous_term_context_resolved(term, category, acceptance, intent, business_flow, entrypoints)
            add("ambiguous_term", category, f"Requirement uses ambiguous term '{term}' and needs concrete business meaning.", required)
    if not str(intent.get("intent") or "").strip():
        add("business_intent", "business_goal", "Business intent is missing; cannot tell what outcome the requirement optimizes.")
    elif intent.get("confidence") != "high":
        add("business_intent", "business_goal", "Business intent is inferred; the real purpose, current pain point, and expected business outcome must be confirmed.")
    if not business_flow:
        add("business_flow", "business_flow", "Business flow is missing; actor, trigger, system behavior, and outcome are unclear.")
    for issue in flow_quality_issues(business_flow):
        add(issue["source"], issue["category"], issue["message"])
    if not entrypoints:
        add("entrypoints", "actor_entrypoint", "Entry point is missing; trigger could be frontend, API, MQ consumer, scheduled job, or manual task.")
    elif not any(item.get("confidence") == "high" for item in entrypoints if isinstance(item, dict)):
        add("entrypoints", "actor_entrypoint", "Entry point is inferred; concrete frontend action, API, scheduled task, MQ consumer, manual task, or external callback must be confirmed.")
    for item in acceptance:
        if not isinstance(item, dict):
            continue
        reason = weak_acceptance_reason(str(item.get("criteria") or ""))
        if reason:
            add("acceptance_criteria", "acceptance", f"{reason}: {item.get('criteria')}")
    state_change_markers = ["状态更新", "更新状态", "状态变更", "状态流转", "状态从", "change status", "update status", "status transition"]
    if any(marker in lower or marker in text for marker in state_change_markers) and not state_transitions:
        add("state_transition", "state_transition", "Status change is mentioned but from/to states are not explicit.")
    return ambiguities


def requirement_understanding_scorecard(
    ambiguities: list[dict[str, str]],
    acceptance: list[dict[str, Any]],
    intent: dict[str, Any],
    business_flow: list[dict[str, Any]],
    entrypoints: list[dict[str, str]],
    current_state: dict[str, Any],
    success_metrics: list[dict[str, str]],
) -> dict[str, Any]:
    required_ambiguities = [item for item in ambiguities if item.get("required") is True]
    high_confidence_flow = bool(business_flow) and all(item.get("confidence") == "high" for item in business_flow if isinstance(item, dict))
    structured_steps = [
        item.get("structured_step")
        for item in business_flow
        if isinstance(item, dict) and isinstance(item.get("structured_step"), dict)
    ]
    high_confidence_entrypoint = any(item.get("confidence") == "high" for item in entrypoints if isinstance(item, dict))
    inferred_acceptance = bool(acceptance) and all(not str(item.get("source_evidence")).startswith("input") for item in acceptance)
    executable_acceptance = [
        item for item in acceptance
        if isinstance(item, dict) and not weak_acceptance_reason(str(item.get("criteria") or ""))
    ]
    current_gaps = as_list(current_state.get("evidence_gaps") if isinstance(current_state, dict) else [])

    intent_score = 90 if intent.get("confidence") == "high" else 55 if intent.get("intent") else 20
    if required_ambiguities:
        intent_score = min(intent_score, 60)
    if success_metrics:
        intent_score = min(100, intent_score + 5)

    flow_score = 85 if high_confidence_flow else 45 if business_flow else 15
    if structured_steps and all(item.get("system_actions") for item in structured_steps if isinstance(item, dict)):
        flow_score = min(100, flow_score + 5)
    if any(item.get("branches") for item in business_flow if isinstance(item, dict)):
        flow_score = min(100, flow_score + 5)

    entrypoint_score = 90 if high_confidence_entrypoint else 45 if entrypoints else 10
    acceptance_score = 85 if executable_acceptance and not inferred_acceptance else 50 if acceptance else 10
    if any(item.get("type") == "negative" for item in acceptance if isinstance(item, dict)):
        acceptance_score = min(100, acceptance_score + 5)

    evidence_score = 90 if not current_gaps else 80
    if current_state.get("known_current_facts") if isinstance(current_state, dict) else False:
        evidence_score = min(100, evidence_score + 10)
    if required_ambiguities:
        evidence_score = min(evidence_score, 60)

    dimensions = {
        "intent_score": intent_score,
        "flow_score": flow_score,
        "entrypoint_score": entrypoint_score,
        "acceptance_score": acceptance_score,
        "evidence_score": evidence_score,
    }
    overall = round(sum(dimensions.values()) / len(dimensions))
    weak_dimensions = [name for name, score in dimensions.items() if score < 80]
    return {
        "overall_score": overall,
        "dimensions": dimensions,
        "weak_dimensions": weak_dimensions,
        "expert_threshold": 80,
    }


def understanding_decision(
    ambiguities: list[dict[str, str]],
    acceptance: list[dict[str, Any]],
    intent: dict[str, Any],
    business_flow: list[dict[str, Any]],
    entrypoints: list[dict[str, str]],
    current_state: dict[str, Any],
    success_metrics: list[dict[str, str]],
) -> dict[str, Any]:
    required_ambiguities = [item for item in ambiguities if item.get("required") is True]
    inferred_acceptance = bool(acceptance) and all(not str(item.get("source_evidence")).startswith("input") for item in acceptance)
    high_confidence_flow = bool(business_flow) and all(item.get("confidence") == "high" for item in business_flow if isinstance(item, dict))
    high_confidence_entrypoint = any(item.get("confidence") == "high" for item in entrypoints if isinstance(item, dict))
    scorecard = requirement_understanding_scorecard(ambiguities, acceptance, intent, business_flow, entrypoints, current_state, success_metrics)
    confidence = "high"
    if required_ambiguities:
        confidence = "low"
    elif inferred_acceptance or str(intent.get("confidence")) != "high" or not high_confidence_flow or not high_confidence_entrypoint or scorecard["weak_dimensions"]:
        confidence = "medium"
    design_allowed = not required_ambiguities
    if not str(intent.get("intent") or "").strip():
        level = "insufficient_context"
    elif not design_allowed:
        level = "clarification_required"
    elif confidence == "high" and not scorecard["weak_dimensions"]:
        level = "expert_ready"
    else:
        level = "clarification_required"
    return {
        "decision": "pass" if design_allowed else "needs_clarification",
        "level": level,
        "design_allowed": design_allowed,
        "implementation_allowed": False if required_ambiguities or inferred_acceptance else True,
        "understanding_confidence": confidence,
        "scorecard": scorecard,
        "overall_score": scorecard["overall_score"],
        "weak_dimensions": scorecard["weak_dimensions"],
        "blockers": required_ambiguities,
        "warnings": [{"source": "acceptance_criteria", "message": "Acceptance is inferred and must be confirmed before implementation."}] if inferred_acceptance else [],
    }


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
    objectives = extract_business_objectives(lines)
    success_metrics = extract_success_metrics(lines)
    intent = infer_business_intent(summary, objectives, requirements, operations, business_objects)
    explicit_intents = explicit_business_intent(lines)
    if explicit_intents:
        intent = {"intent": explicit_intents[0]["intent"], "source_evidence": "input", "confidence": "high", "inference": "explicit_business_intent"}
    entrypoints = extract_entrypoints(text, lines, impact_surface)
    business_flow = extract_business_flow(lines, sorted(set(actors)), entrypoints, acceptance, summary)
    current_business_state = extract_current_business_state(text, lines, entrypoints, impact_surface)
    scenarios = extract_user_scenarios(lines, sorted(set(actors)))
    negative_acceptance = [item for item in acceptance if item.get("type") == "negative"]
    rule_conflicts = detect_rule_conflicts(rules)
    implicit_constraints = infer_implicit_constraints(impact_surface, business_objects, data_fields)
    compatibility_constraints = extract_prefixed(lines, ("compatibility", "兼容", "backward compatible", "向后兼容"))
    derived_constraint_questions = constraint_questions(implicit_constraints, questions)
    readiness_gaps = expert_readiness_gaps(impact_surface, acceptance, objectives, scenarios, risks, compatibility_constraints)
    ambiguities = detect_ambiguities(text, acceptance, intent, business_flow, entrypoints, state_transitions)
    requirements_understanding = understanding_decision(ambiguities, acceptance, intent, business_flow, entrypoints, current_business_state, success_metrics)
    understanding_evidence = fact_assumption_split(intent, business_flow, entrypoints, acceptance, assumptions)
    decision_blocked = bool(questions or rule_conflicts or not requirements_understanding["design_allowed"])
    return {
        "schema": SCHEMA,
        "doc_id": doc_id,
        "title": title,
        "lane": lane,
        "requirement_summary": summary,
        "business_intent": intent,
        "business_problem": explicit_intents[0]["intent"] if explicit_intents else intent.get("intent", ""),
        "expected_business_outcome": intent.get("intent", ""),
        "business_flow": business_flow,
        "business_flow_model": {
            "steps": [item.get("structured_step") for item in business_flow if isinstance(item, dict) and item.get("structured_step")],
            "branches": [branch for item in business_flow if isinstance(item, dict) for branch in as_list(item.get("branches"))] + detect_flow_branches(text),
            "entrypoint_count": len(entrypoints),
            "supports_multiple_entrypoints": len(entrypoints) > 1,
        },
        "entrypoints": entrypoints,
        "trigger_conditions": [item.get("trigger") for item in entrypoints if isinstance(item, dict) and item.get("trigger")],
        "current_business_state": current_business_state,
        "preconditions": extract_prefixed(lines, ("precondition", "preconditions", "前置条件")),
        "postconditions": [str(item.get("expected_outcome")) for item in business_flow if isinstance(item, dict) and item.get("expected_outcome")],
        "ambiguities": ambiguities,
        "requirements_understanding": requirements_understanding,
        "requirements_understanding_evidence": understanding_evidence,
        "confirmed_facts": understanding_evidence["confirmed_facts"],
        "inferred_assumptions": understanding_evidence["inferred_assumptions"],
        "unresolved_points": understanding_evidence["unresolved_points"],
        "understanding_confidence": requirements_understanding["understanding_confidence"],
        "design_allowed": requirements_understanding["design_allowed"],
        "implementation_allowed": requirements_understanding["implementation_allowed"],
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
        "success_metrics": success_metrics,
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
        "decision": "blocked" if decision_blocked else "ready_for_design",
        "next_action": "Resolve requirement clarification blockers before design." if decision_blocked else "Proceed to technical and architecture design.",
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
    understanding = spec.get("requirements_understanding") if isinstance(spec.get("requirements_understanding"), dict) else {}
    if understanding and understanding.get("design_allowed") is False:
        blockers.append({"source": "requirements_understanding", "message": "business intent, flow, entrypoint, or acceptance ambiguity must be clarified before design", "count": len(as_list(understanding.get("blockers")))})
    if not spec.get("business_intent") or not str((spec.get("business_intent") or {}).get("intent") if isinstance(spec.get("business_intent"), dict) else spec.get("business_intent")).strip():
        blockers.append({"source": "business_intent", "message": "business intent is required before design"})
    if not as_list(spec.get("business_flow")):
        blockers.append({"source": "business_flow", "message": "business flow is required before design"})
    if not as_list(spec.get("entrypoints")):
        blockers.append({"source": "entrypoints", "message": "at least one entrypoint or trigger path is required before design"})
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
