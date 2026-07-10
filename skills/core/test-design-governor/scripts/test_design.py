#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-test-design-v1"
SIGNAL_KEYWORDS = {
    "ui": ["ui", "page", "route", "frontend", "browser", "页面", "列表", "按钮", "展示", "筛选", "导入", "前端"],
    "api": ["api", "接口", "endpoint", "request", "response"],
    "data": ["database", "db", "sql", "字段", "数据", "记录", "迁移", "排序", "状态"],
}
DIRECT_SIGNAL_KEYWORDS = {
    "permission": ["permission", "role", "tenant", "unauthorized", "admin", "权限", "角色", "租户", "越权", "未授权"],
    "import": ["import", "导入", "批量", "upload", "上传"],
    "filter": ["filter", "筛选", "query", "查询", "搜索"],
}
SEMANTIC_REF_FIELDS = {
    "ui_refs": ["page_or_route"],
    "api_refs": ["contract"],
    "data_refs": ["slice", "id", "read_rule", "write_rule", "migration", "field", "table"],
    "permission_refs": ["role", "rule", "negative_case"],
    "module_refs": ["module", "responsibility"],
    "repo_refs": ["repo", "responsibility"],
}


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def text_of(*values: Any) -> str:
    return json.dumps(values, ensure_ascii=False).lower()


def signal_flags(*values: Any) -> dict[str, bool]:
    text = text_of(*values)
    direct_text = text_of(values[0]) if values else text
    flags = {name: any(term in text for term in terms) for name, terms in SIGNAL_KEYWORDS.items()}
    flags.update({name: any(term in direct_text for term in terms) for name, terms in DIRECT_SIGNAL_KEYWORDS.items()})
    return flags


def extract_field_names(title: str) -> list[str]:
    names = re.findall(r"`([^`]+)`", title)
    quoted = re.findall(r"[「“]([^」”]+)[」”]", title)
    result: list[str] = []
    for value in names + quoted:
        cleaned = value.strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


def unique_compact(values: list[str], limit: int = 4) -> list[str]:
    result: list[str] = []
    for value in values:
        cleaned = " ".join(str(value or "").strip().split())
        if cleaned and cleaned not in result:
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def dict_values(items: list[Any], fields: list[str], limit: int = 4) -> list[str]:
    values: list[str] = []
    for item in items:
        if isinstance(item, dict):
            for field in fields:
                value = item.get(field)
                if value not in (None, "", [], {}):
                    values.append(str(value))
        elif item not in (None, "", [], {}):
            values.append(str(item))
    return unique_compact(values, limit)


def normalize_context_ref(value: str) -> str:
    rendered = str(value or "").strip()
    rendered = re.sub(r"\bread through\s+(.+)$", r"读取 \1", rendered)
    rendered = re.sub(r"\bwrite through\s+(.+?)\s+only if this slice changes state$", r"仅当该切片改变状态时写入 \1", rendered)
    rendered = re.sub(r"\bnone unless this slice changes schema/data backfill$", "无，除非该切片涉及结构变更或数据回填", rendered)
    rendered = rendered.replace(" only if this slice changes state", "，仅当该切片改变状态")
    rendered = rendered.replace(" unless this slice changes schema/data backfill", "，除非该切片涉及结构变更或数据回填")
    return rendered


def normalize_context_refs(values: list[str]) -> list[str]:
    return unique_compact([normalize_context_ref(value) for value in values])


def values_for_breakdown(items: list[Any], fields: list[str], breakdown_id: str | None) -> list[str]:
    rows = [item for item in items if isinstance(item, dict)]
    if breakdown_id:
        matched = [item for item in rows if breakdown_id.lower() in text_of(item)]
        if matched:
            return dict_values(matched, fields)
    return dict_values(rows, fields, limit=2)


def requirements_understanding_gate(spec: dict[str, Any], technical: dict[str, Any], architecture: dict[str, Any]) -> dict[str, Any]:
    tech_gate = technical.get("requirements_understanding_gate") if isinstance(technical.get("requirements_understanding_gate"), dict) else {}
    arch_gate = architecture.get("requirements_understanding_gate") if isinstance(architecture.get("requirements_understanding_gate"), dict) else {}
    spec_understanding = spec.get("requirements_understanding") if isinstance(spec.get("requirements_understanding"), dict) else {}
    gate = arch_gate or tech_gate
    if not gate and not spec_understanding and "design_allowed" not in spec and "implementation_allowed" not in spec:
        return {}
    design_allowed = bool(spec.get("design_allowed", gate.get("design_allowed", spec_understanding.get("design_allowed", True))))
    implementation_allowed = bool(spec.get("implementation_allowed", gate.get("implementation_allowed", spec_understanding.get("implementation_allowed", design_allowed))))
    return {
        "decision": gate.get("decision") or spec_understanding.get("decision") or ("pass" if design_allowed else "needs_clarification"),
        "design_allowed": design_allowed,
        "implementation_allowed": implementation_allowed and design_allowed,
        "understanding_confidence": spec.get("understanding_confidence") or gate.get("understanding_confidence") or spec_understanding.get("understanding_confidence") or spec_understanding.get("confidence") or ("high" if design_allowed else "low"),
        "business_intent": spec.get("business_intent") or gate.get("business_intent") or spec_understanding.get("business_intent") or "",
        "business_flow": spec.get("business_flow") or gate.get("business_flow") or spec_understanding.get("business_flow") or [],
        "entrypoints": spec.get("entrypoints") or gate.get("entrypoints") or spec_understanding.get("entrypoints") or [],
        "trigger_conditions": spec.get("trigger_conditions") or gate.get("trigger_conditions") or spec_understanding.get("trigger_conditions") or [],
        "blockers": as_list(gate.get("blockers")) or as_list(spec_understanding.get("blockers")),
        "ambiguities": as_list(gate.get("ambiguities")) or as_list(spec.get("ambiguities")),
        "required_action": "resolve requirement clarification questions before test design can be executable" if not design_allowed else "none",
    }


class TestContext:
    def __init__(
        self,
        *,
        ui_refs: list[str],
        api_refs: list[str],
        data_refs: list[str],
        permission_refs: list[str],
        module_refs: list[str],
        repo_refs: list[str],
        field_refs: list[str],
    ) -> None:
        self.ui_refs = ui_refs
        self.api_refs = api_refs
        self.data_refs = data_refs
        self.permission_refs = permission_refs
        self.module_refs = module_refs
        self.repo_refs = repo_refs
        self.field_refs = field_refs

    @classmethod
    def from_designs(
        cls,
        technical: dict[str, Any],
        architecture: dict[str, Any],
        title: str,
        acceptance_index: int | None = None,
    ) -> "TestContext":
        breakdown_id = f"BRK-{acceptance_index + 1}" if acceptance_index is not None else None
        data_refs = normalize_context_refs(
            values_for_breakdown(as_list(technical.get("data_design")), SEMANTIC_REF_FIELDS["data_refs"], breakdown_id)
        )
        permission_refs = dict_values(as_list(technical.get("permission_model")), SEMANTIC_REF_FIELDS["permission_refs"])
        return cls(
            ui_refs=dict_values(as_list(technical.get("ui_ue_design")), SEMANTIC_REF_FIELDS["ui_refs"]),
            api_refs=dict_values(as_list(technical.get("api_contracts")), SEMANTIC_REF_FIELDS["api_refs"]),
            data_refs=data_refs,
            permission_refs=permission_refs if signal_flags(title)["permission"] else [],
            module_refs=dict_values(as_list(technical.get("module_decomposition")), SEMANTIC_REF_FIELDS["module_refs"]),
            repo_refs=dict_values(as_list(architecture.get("repo_responsibilities")), SEMANTIC_REF_FIELDS["repo_refs"]),
            field_refs=extract_field_names(title),
        )

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "ui_refs": self.ui_refs,
            "api_refs": self.api_refs,
            "data_refs": self.data_refs,
            "permission_refs": self.permission_refs,
            "module_refs": self.module_refs,
            "repo_refs": self.repo_refs,
            "field_refs": self.field_refs,
        }


def build_test_context(technical: dict[str, Any], architecture: dict[str, Any], title: str, acceptance_index: int | None = None) -> dict[str, list[str]]:
    return TestContext.from_designs(technical, architecture, title, acceptance_index).as_dict()


def clean_acceptance_title(value: str) -> str:
    title = str(value or "").strip()
    prefixes = [
        "User-visible behavior matches:",
        "user-visible behavior matches:",
        "AC:",
        "需求：",
        "验证：",
        "回归验证：",
    ]
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if title.startswith(prefix):
                title = title[len(prefix):].strip()
                changed = True
    return title or "验收标准"


def is_weak_acceptance_title(title: str) -> bool:
    compact = clean_acceptance_title(title).strip().lower()
    return compact in {"", "标准", "验收标准", "acceptance", "acceptance criteria", "expected behavior", "需求"}


def functional_case_title(title: str) -> str:
    return f"验证：{clean_acceptance_title(title)}"


def regression_case_title(title: str) -> str:
    return f"回归验证：{clean_acceptance_title(title)} 不破坏既有行为"


def case_steps(title: str, context: dict[str, list[str]] | None = None) -> list[str]:
    target = clean_acceptance_title(title)
    context = context or {}
    flags = signal_flags(target, context)
    steps = [f"创建覆盖该验收条件的合成数据，记录业务主键和数据状态：{target}"]
    if flags["ui"]:
        ui = "、".join(context.get("ui_refs") or []) or "受影响页面"
        steps.append(f"从真实菜单或路由进入 `{ui}`，执行页面操作：{target}")
        if flags["filter"]:
            steps.append("设置筛选条件并触发查询，记录请求参数和页面结果数量")
        if flags["import"]:
            steps.append("上传或录入批量数据，确认页面提示、失败明细和成功数量")
    if flags["api"]:
        api = "、".join(context.get("api_refs") or []) or "受影响接口"
        steps.append(f"使用代表性请求调用 `{api}`，记录请求参数、响应码和响应体：{target}")
    if flags["data"]:
        data = "、".join(context.get("data_refs") or context.get("field_refs") or []) or "受影响数据"
        steps.append(f"查询或导出 `{data}`，核对字段值、状态过滤、排序或持久化结果")
    if flags["permission"]:
        permission = "、".join(context.get("permission_refs") or []) or "授权与未授权账号"
        steps.append(f"分别使用 `{permission}` 执行同一动作，核对可见性、响应码和审计记录")
    steps.append(f"按验收口径逐项核对页面、接口、数据或导出结果：{target}")
    return steps


def data_ref(case_id: str) -> str:
    return f"TD-{case_id}"


def regression_steps(title: str) -> list[str]:
    target = clean_acceptance_title(title)
    return [
        f"准备与该场景相邻的既有基线数据：{target}",
        f"执行与「{target}」相邻的既有流程",
        "确认既有行为、兼容性和本次验收结果均未被破坏",
    ]


def assertion_points(title: str, context: dict[str, list[str]] | None = None) -> list[str]:
    target = clean_acceptance_title(title)
    context = context or {}
    flags = signal_flags(target, context)
    points = [f"验收描述可被直接观察或用证据复现：{target}"]
    fields = unique_compact(extract_field_names(target) + as_list(context.get("field_refs")))
    if fields:
        points.append(f"关键字段取值正确：{', '.join(fields)}")
    if flags["ui"]:
        ui = "、".join(context.get("ui_refs") or []) or "页面"
        points.append(f"`{ui}` 的展示、交互状态、提示文案和列表数量符合预期")
    if flags["api"]:
        api = "、".join(context.get("api_refs") or []) or "接口"
        points.append(f"`{api}` 的响应码、响应结构、错误语义和兼容字段符合预期")
    if flags["data"]:
        data = "、".join(context.get("data_refs") or []) or "数据库/导出/查询结果"
        points.append(f"`{data}` 中的字段、状态过滤和排序符合预期")
    if flags["permission"]:
        permission = "、".join(context.get("permission_refs") or []) or "权限规则"
        points.append(f"`{permission}` 下授权账号可操作，未授权账号不可见或被拒绝")
    return points


def data_strategy(case_id: str, title: str, case_type: str = "functional", context: dict[str, list[str]] | None = None) -> dict[str, Any]:
    target = clean_acceptance_title(title)
    context = context or {}
    flags = signal_flags(target, case_type, context)
    setup_methods = ["fixture_or_factory"]
    record_target = "、".join(context.get("data_refs") or context.get("field_refs") or []) or "覆盖验收条件"
    records = [{"name": f"{case_id} 主记录", "state": record_target, "source": "synthetic fixture"}]
    accounts: list[dict[str, str]] = []
    if flags["permission"] or case_type == "permission":
        permission = "、".join(context.get("permission_refs") or []) or "权限边界"
        accounts = [
            {"role": "authorized-user", "purpose": f"验证允许路径：{permission}"},
            {"role": "restricted-user", "purpose": f"验证拒绝路径：{permission}"},
        ]
    if flags["import"]:
        setup_methods.append("upload_fixture_file")
        records.append({"name": f"{case_id} 批量导入明细", "state": "包含成功和失败样本", "source": "synthetic file"})
    if flags["filter"]:
        records.append({"name": f"{case_id} 对照记录", "state": "不满足筛选条件", "source": "synthetic fixture"})
    return {
        "dataset_ref": data_ref(case_id),
        "setup_methods": setup_methods,
        "records": records,
        "accounts": accounts,
        "cleanup": [f"按业务主键删除 {data_ref(case_id)} 合成记录", "撤销临时账号/角色绑定"],
        "privacy": ["synthetic/anonymized only", "no live identifiers or credentials in fixture metadata"],
    }


def execution_path(title: str, case_type: str = "functional", context: dict[str, list[str]] | None = None) -> list[str]:
    target = clean_acceptance_title(title)
    context = context or {}
    flags = signal_flags(target, case_type, context)
    path: list[str] = []
    if flags["ui"]:
        ui = "、".join(context.get("ui_refs") or []) or "受影响页面/菜单"
        path.append(f"UI: 打开 {ui} -> 设置条件/执行动作 -> 观察页面状态")
    if flags["api"]:
        api = "、".join(context.get("api_refs") or []) or "受影响接口"
        path.append(f"API: 构造请求 -> 调用 {api} -> 校验响应与兼容性")
    if flags["data"]:
        data = "、".join(context.get("data_refs") or context.get("field_refs") or []) or "持久化/查询/导出结果"
        path.append(f"DATA: 准备记录 -> 执行业务动作 -> 校验 {data}")
    if flags["permission"] or case_type == "permission":
        permission = "、".join(context.get("permission_refs") or []) or "授权账号正向验证 -> 受限账号反向验证"
        path.append(f"PERMISSION: {permission}")
    return path or ["BUSINESS: 准备代表性数据 -> 执行业务入口 -> 核对验收结果"]


def acceptance_case(case_id: str, ac_id: str, title: str, evidence: list[Any], context: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "id": case_id,
        "acceptance_id": ac_id,
        "type": "functional",
        "execution_required": "must_run",
        "execution_mode": "automated_or_manual",
        "title": functional_case_title(title),
        "preconditions": [f"测试数据 {data_ref(case_id)} 已创建"],
        "test_data_refs": [data_ref(case_id)],
        "data_requirements": [{"kind": "representative_record", "description": f"用于验证「{title}」的合成数据"}],
        "data_setup_strategy": data_strategy(case_id, title, context=context),
        "execution_path": execution_path(title, context=context),
        "semantic_refs": context,
        "setup_preconditions": [f"执行前创建 {data_ref(case_id)}"],
        "cleanup_expectations": [f"执行后清理 {data_ref(case_id)}"],
        "steps": case_steps(title, context=context),
        "assertion_points": assertion_points(title, context=context),
        "expected_result": f"满足验收：{title}",
        "evidence_required": evidence,
    }


def regression_case(case_id: str, ac_id: str, title: str, evidence: list[Any], context: dict[str, list[str]]) -> dict[str, Any]:
    return {
        "id": case_id,
        "acceptance_id": ac_id,
        "type": "regression",
        "execution_required": "must_run",
        "execution_mode": "automated_or_manual",
        "title": regression_case_title(title),
        "preconditions": ["相邻既有行为可执行", f"测试数据 {data_ref(case_id)} 已创建"],
        "test_data_refs": [data_ref(case_id)],
        "data_requirements": [{"kind": "baseline_record", "description": f"与「{title}」相邻的既有基线数据"}],
        "data_setup_strategy": data_strategy(case_id, title, "regression", context),
        "execution_path": execution_path(title, "regression", context),
        "semantic_refs": context,
        "setup_preconditions": [f"执行前创建 {data_ref(case_id)}"],
        "cleanup_expectations": [f"执行后清理 {data_ref(case_id)}"],
        "steps": regression_steps(title),
        "assertion_points": assertion_points(title, context),
        "expected_result": "既有行为保持兼容，且本次验收仍通过",
        "evidence_required": sorted(set(evidence + ["regression evidence"])),
    }


def permission_case() -> dict[str, Any]:
    case_id = "TC-PERM-1"
    title = "未授权角色不能访问或触发本次变更行为"
    return {
        "id": case_id,
        "acceptance_id": "",
        "type": "permission",
        "execution_required": "must_run",
        "execution_mode": "automated_or_manual",
        "title": title,
        "preconditions": ["准备受限角色账号", f"测试数据 {data_ref(case_id)} 已创建"],
        "test_data_refs": [data_ref(case_id)],
        "data_requirements": [{"kind": "restricted_account", "description": "受限角色或账号合成数据"}],
        "data_setup_strategy": data_strategy(case_id, title, "permission"),
        "execution_path": execution_path(title, "permission"),
        "setup_preconditions": [f"执行前创建 {data_ref(case_id)}"],
        "cleanup_expectations": [f"执行后清理 {data_ref(case_id)}"],
        "steps": ["使用受限角色登录或调用接口", "尝试访问或触发本次变更行为", "确认入口不可见、访问被拒绝或操作被阻止，并保留反向权限证据"],
        "assertion_points": ["受限角色入口不可见或请求被拒绝", "授权角色原有路径仍可使用", "权限拒绝证据可追溯到角色/租户"],
        "expected_result": "访问被拒绝、入口不可见或操作被阻止",
        "evidence_required": ["permission test evidence"],
    }


def integration_case() -> dict[str, Any]:
    case_id = "TC-INT-1"
    title = "跨组件/跨仓集成契约保持兼容"
    return {
        "id": case_id,
        "acceptance_id": "",
        "type": "integration",
        "execution_required": "must_run",
        "execution_mode": "automated_or_manual",
        "title": title,
        "preconditions": ["受影响组件已部署到同一验证环境", f"测试数据 {data_ref(case_id)} 已创建"],
        "test_data_refs": [data_ref(case_id)],
        "data_requirements": [{"kind": "integration_fixture", "description": "跨组件/跨仓集成合成数据"}],
        "data_setup_strategy": data_strategy(case_id, title, "integration"),
        "execution_path": ["INTEGRATION: 从消费方入口触发端到端流程 -> 观察上游响应和下游处理"],
        "setup_preconditions": [f"执行前创建 {data_ref(case_id)}"],
        "cleanup_expectations": [f"执行后清理 {data_ref(case_id)}"],
        "steps": ["从消费方入口触发端到端业务流程", "观察生产方接口、消费方处理和错误兜底", "确认上下游契约、响应语义和错误处理保持兼容"],
        "assertion_points": ["消费方调用成功或按预期降级", "生产方响应结构和错误语义兼容", "跨组件日志和证据可追溯"],
        "expected_result": "上下游契约、响应语义和错误处理保持兼容",
        "evidence_required": ["integration test evidence"],
    }


def frontend_case() -> dict[str, Any]:
    case_id = "TC-UI-1"
    title = "浏览器验收：变更页面交互和展示符合预期"
    return {
        "id": case_id,
        "acceptance_id": "",
        "type": "frontend",
        "execution_required": "must_run",
        "execution_mode": "browser_acceptance",
        "title": title,
        "preconditions": ["前端应用已启动", f"测试数据 {data_ref(case_id)} 已创建"],
        "test_data_refs": [data_ref(case_id)],
        "data_requirements": [{"kind": "ui_fixture", "description": "页面可见状态合成数据"}],
        "data_setup_strategy": data_strategy(case_id, title, "frontend"),
        "execution_path": ["UI: 打开受影响页面/路由 -> 执行交互 -> 检查页面状态和浏览器错误"],
        "setup_preconditions": [f"执行前创建 {data_ref(case_id)}"],
        "cleanup_expectations": [f"执行后清理 {data_ref(case_id)}"],
        "steps": ["打开受影响页面或路由", "执行本次需求涉及的交互", "检查页面状态、控制台错误和失败网络请求"],
        "assertion_points": ["页面状态和交互结果符合预期", "无控制台错误", "无失败网络请求"],
        "expected_result": "页面行为正确，且无控制台或网络异常",
        "evidence_required": ["frontend_acceptance.json"],
    }


def render(spec: dict[str, Any], technical: dict[str, Any], architecture: dict[str, Any]) -> dict[str, Any]:
    acceptance = [item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]
    requirements = [item for item in as_list(spec.get("requirements")) if isinstance(item, dict)]
    signals = text_of(spec, technical, architecture)
    gate = requirements_understanding_gate(spec, technical, architecture)
    cases: list[dict[str, Any]] = []
    for idx, ac in enumerate(acceptance or [{"id": "AC-1", "criteria": spec.get("requirement_summary", "")}]):
        ac_id = str(ac.get("id") or f"AC-{idx + 1}")
        title = clean_acceptance_title(str(ac.get("criteria") or ac.get("summary") or "验收标准"))
        context = build_test_context(technical, architecture, title, idx)
        evidence = as_list(ac.get("evidence_required")) or ["test execution evidence"]
        case_id = f"TC-{idx + 1}"
        reg_case_id = f"TC-{idx + 1}-REG"
        cases.append(acceptance_case(case_id, ac_id, title, evidence, context))
        cases.append(regression_case(reg_case_id, ac_id, title, evidence, context))
    if any(term in signals for term in ["permission", "role", "tenant", "权限", "角色", "租户"]):
        cases.append(permission_case())
    if len(as_list(architecture.get("repo_responsibilities"))) > 1 or "cross" in signals:
        cases.append(integration_case())
    if any(term in signals for term in ["ui", "page", "route", "frontend", "browser"]):
        cases.append(frontend_case())
    return {
        "schema": SCHEMA,
        "doc_id": spec.get("doc_id") or technical.get("doc_id") or architecture.get("doc_id"),
        "title": spec.get("title") or technical.get("title") or architecture.get("title"),
        "decision": "block" if gate.get("design_allowed") is False or gate.get("implementation_allowed") is False else "pass",
        "requirements_understanding_gate": gate,
        "requirement_count": len(requirements),
        "acceptance_count": len(acceptance),
        "test_cases": cases,
        "regression_scope": [{"area": "affected behavior", "reason": "changed requirement path"}],
        "integration_scope": [case for case in cases if case["type"] == "integration"],
        "frontend_scope": [case for case in cases if case["type"] == "frontend"],
        "permission_scope": [case for case in cases if case["type"] == "permission"],
        "evidence_required": sorted({e for case in cases for e in as_list(case.get("evidence_required"))}),
        "test_data_required": any(as_list(case.get("test_data_refs")) for case in cases),
        "test_data_plan_ref": "test_data_plan.json",
        "open_risks": [
            {"source": "requirements_understanding_gate", "message": "requirement understanding is not sufficient for executable test design", "gate": gate}
        ] if gate.get("design_allowed") is False or gate.get("implementation_allowed") is False else [],
    }


def validate_design(data: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if data.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    gate = data.get("requirements_understanding_gate") if isinstance(data.get("requirements_understanding_gate"), dict) else {}
    if gate.get("design_allowed") is False:
        blockers.append({"source": "requirements_understanding_gate", "message": "requirement understanding blocks executable test design", "gate": gate})
    if gate.get("implementation_allowed") is False:
        blockers.append({"source": "requirements_understanding_gate", "message": "requirement understanding blocks test execution planning", "gate": gate})
    cases = [item for item in as_list(data.get("test_cases")) if isinstance(item, dict)]
    if not cases:
        blockers.append({"source": "test_cases", "message": "at least one test case is required"})
    acceptance_count = int(data.get("acceptance_count") or 0)
    mapped = {case.get("acceptance_id") for case in cases if case.get("acceptance_id")}
    if acceptance_count and len(mapped) < acceptance_count:
        blockers.append({"source": "traceability", "message": "not every acceptance criterion has a mapped test", "mapped": len(mapped), "acceptance_count": acceptance_count})
    for idx, case in enumerate(cases):
        for key in ["id", "type", "title", "steps", "expected_result", "evidence_required"]:
            if not case.get(key):
                blockers.append({"source": f"test_cases[{idx}].{key}", "message": f"{key} is required"})
        if case.get("execution_required") not in {"must_run", "optional", "manual", "blocked"}:
            blockers.append({"source": f"test_cases[{idx}].execution_required", "message": "execution_required must be must_run/optional/manual/blocked"})
        if case.get("acceptance_id") and case.get("execution_required") != "must_run":
            blockers.append({"source": f"test_cases[{idx}].execution_required", "message": "acceptance-mapped cases must be marked must_run"})
        if case.get("acceptance_id") and is_weak_acceptance_title(str(case.get("title") or case.get("expected_result") or "")):
            blockers.append({"source": f"test_cases[{idx}].acceptance", "message": "weak acceptance criteria such as '标准' are not executable"})
        if case.get("data_requirements") and not case.get("test_data_refs"):
            blockers.append({"source": f"test_cases[{idx}].test_data_refs", "message": "test_data_refs are required when data_requirements exist"})
        if case.get("test_data_refs") and not case.get("cleanup_expectations"):
            blockers.append({"source": f"test_cases[{idx}].cleanup_expectations", "message": "cleanup expectations are required when test data is used"})
        if case.get("acceptance_id") and not as_list(case.get("assertion_points")):
            blockers.append({"source": f"test_cases[{idx}].assertion_points", "message": "assertion_points are required for acceptance-mapped cases"})
        if case.get("acceptance_id") and not as_list(case.get("execution_path")):
            blockers.append({"source": f"test_cases[{idx}].execution_path", "message": "execution_path is required for acceptance-mapped cases"})
        if case.get("test_data_refs") and not isinstance(case.get("data_setup_strategy"), dict):
            blockers.append({"source": f"test_cases[{idx}].data_setup_strategy", "message": "data_setup_strategy is required when test data is used"})
    generic_steps = {"prepare data", "execute affected behavior", "verify expected result"}
    for idx, case in enumerate(cases):
        steps = {str(item).strip().lower() for item in as_list(case.get("steps"))}
        if steps & generic_steps:
            blockers.append({"source": f"test_cases[{idx}].steps", "message": "generic test steps are not allowed"})
    if acceptance_count:
        for ac_id in mapped:
            if not any(case.get("acceptance_id") == ac_id and case.get("type") == "regression" for case in cases):
                blockers.append({"source": "regression_mapping", "message": f"acceptance criterion lacks regression coverage: {ac_id}"})
    if not data.get("regression_scope"):
        warnings.append({"source": "regression_scope", "message": "regression scope is recommended"})
    decision = "block" if blockers else "pass"
    return {"schema": "codex-test-design-validation-v1", "decision": decision, "blockers": blockers, "warnings": warnings}


def main() -> int:
    parser = argparse.ArgumentParser(description="Render or validate test design")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_render = sub.add_parser("render")
    p_render.add_argument("--spec", required=True)
    p_render.add_argument("--technical-design", required=True)
    p_render.add_argument("--architecture-design", required=True)
    p_render.add_argument("--out", required=True)
    p_val = sub.add_parser("validate")
    p_val.add_argument("--file", required=True)
    p_val.add_argument("--out")
    args = parser.parse_args()
    if args.cmd == "render":
        result = render(load_json(Path(args.spec)), load_json(Path(args.technical_design)), load_json(Path(args.architecture_design)))
        write_json(Path(args.out), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    result = validate_design(load_json(Path(args.file)))
    if args.out:
        write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
