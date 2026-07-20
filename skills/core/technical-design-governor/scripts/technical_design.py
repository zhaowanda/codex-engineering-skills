#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

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
GENERIC_ENTRYPOINT_PARTS = {
    "assets",
    "icons",
    "plugins",
    "config",
    "node_modules",
}
DOMAIN_HINTS = {
    "renewal": ["renew", "renewal", "续期", "续费", "到期", "expired", "settlement", "结算", "pool", "设备"],
    "order": ["order", "订单", "结算订单", "回款"],
    "batch": ["batch", "批量", "导入", "import"],
    "menu": ["menu", "菜单", "click", "tracking", "埋点"],
    "device": ["device", "设备", "imei", "terminal"],
}
DATA_TERMS = ["字段", "数据库", "表", "数据", "迁移", "状态", "金额", "结算", "回填", "索引", "唯一", "外键", "月份", "历史", "database", "table", "field", "schema", "migration", "status", "amount"]
SYSTEM_TERMS = ["跨系统", "第三方", "上下游", "调用", "接口", "api", "service", "provider", "consumer", "同步", "异步", "飞书", "审批流", "审批回调", "回调"]
MQ_TERMS = ["mq", "消息", "topic", "queue", "producer", "consumer", "kafka", "rocketmq", "rabbitmq", "事件", "发布", "订阅", "消费"]
CACHE_TERMS = ["缓存", "cache", "redis", "高频", "热点", "慢查询", "统计", "列表", "字典", "配置", "命中率"]
CONSISTENCY_TERMS = ["事务", "一致性", "幂等", "重试", "补偿", "对账", "多表", "多系统", "写入", "回滚", "结算", "金额", "transaction", "consistency", "idempotency", "retry", "compensation", "rollback", "settlement", "payment", "commit"]


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def json_text(*values: Any) -> str:
    return json.dumps(values, ensure_ascii=False).lower()


def has_any_signal(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower or term in text for term in terms)


def impact_signals(spec: dict[str, Any], breakdown: list[dict[str, Any]], route_refs: list[str]) -> dict[str, bool]:
    applicability = {
        str(item.get("area") or ""): str(item.get("status") or "")
        for item in as_list(spec.get("impact_applicability"))
        if isinstance(item, dict) and item.get("area")
    }
    blob = " ".join([
        str(spec.get("title") or ""),
        str(spec.get("requirement_summary") or ""),
        json_text(
            spec.get("business_objects"),
            spec.get("operations"),
            spec.get("business_flow"),
            spec.get("business_rules"),
            spec.get("acceptance_criteria"),
            spec.get("source_trace"),
            spec.get("external_references"),
        ),
        " ".join(str(item.get("summary") or "") for item in breakdown),
        " ".join(route_refs),
    ])
    impact_areas = {area for area, status in applicability.items() if status == "required"}
    if not applicability:
        impact_areas = {str(item.get("area") or "") for item in as_list(spec.get("impact_surface")) if isinstance(item, dict)}
    return {
        "data": "data" in impact_areas or (not applicability and has_any_signal(blob, DATA_TERMS)),
        "system": "api" in impact_areas or has_any_signal(blob, SYSTEM_TERMS) or len(route_refs) > 0,
        "mq": has_any_signal(blob, MQ_TERMS),
        "cache": "performance" in impact_areas or has_any_signal(blob, CACHE_TERMS),
        "consistency": has_any_signal(blob, CONSISTENCY_TERMS),
        "observability": True,
    }


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def source_lines(spec: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for item in as_list(spec.get("source_trace")):
        if isinstance(item, dict):
            value = item.get("text") or item.get("line") or item.get("content")
            if value:
                lines.append(str(value).strip())
        elif item:
            lines.append(str(item).strip())
    source = spec.get("source")
    if isinstance(source, dict):
        raw = source.get("text") or source.get("content")
        if isinstance(raw, str):
            lines.extend(line.strip() for line in raw.splitlines() if line.strip())
    return [line for line in lines if line]


def actionable_lines(spec: dict[str, Any]) -> list[str]:
    prefixes = ("req:", "requirement:", "rule:", "ac:", "goal:", "scenario:", "- ", "* ")
    skip_prefixes = ("来源", "说明", "文档", "约束", "用户原始需求")
    workflow_terms = ("需求归一化", "技术设计", "架构设计", "测试设计", "交付计划", "代码修改", "拉取 Git", "Git 分支", "文档使用中文")
    lines = []
    for line in source_lines(spec):
        stripped = line.strip()
        low = stripped.lower()
        if any(stripped.startswith(prefix) for prefix in skip_prefixes):
            continue
        if any(term in stripped for term in workflow_terms):
            continue
        if any(low.startswith(prefix) for prefix in prefixes) or any(token in stripped for token in ["新增", "隐藏", "排序", "导入", "填写", "筛选", "续期", "结算", "过期", "权限"]):
            lines.append(re.sub(r"^\s*[-*]\s*", "", stripped))
    return lines


def requirement_breakdown(spec: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add_row(summary: str, source: str, source_id: str = "") -> None:
        clean = re.sub(r"^(req|requirement|rule|ac|goal|scenario)\s*[:：]\s*", "", summary.strip(), flags=re.I)
        clean = clean.strip(" -\t")
        workflow_terms = ("需求归一化", "技术设计", "架构设计", "测试设计", "交付计划", "代码修改", "拉取 Git", "Git 分支", "文档使用中文")
        if clean in {"需求", "验收", "标准", "约束"} or clean.startswith(("来源", "说明", "文档使用", "本次需求涉及", "关联仓库")):
            return
        if any(term in clean for term in workflow_terms):
            return
        if len(clean) < 4:
            return
        if source == "spec.requirements" and rows and str(rows[-1].get("summary") or "").endswith("包括：") and len(clean) <= 20:
            return
        if not clean or clean.lower() in seen:
            return
        seen.add(clean.lower())
        idx = len(rows) + 1
        lower = clean.lower()
        impact = []
        if any(token in lower or token in clean for token in ["api", "接口", "endpoint"]):
            impact.append("api")
        if any(token in lower or token in clean for token in ["页面", "按钮", "表格", "ui", "筛选", "排序", "展示", "隐藏"]):
            impact.append("ui")
        if any(token in lower or token in clean for token in ["字段", "数据库", "表", "数据", "迁移", "状态", "到期时间", "月份"]):
            impact.append("data")
        if any(token in lower or token in clean for token in ["权限", "角色", "租户", "admin", "operator"]):
            impact.append("permission")
        if any(token in lower or token in clean for token in ["导入", "批量", "结算", "回款", "续期", "续费"]):
            impact.append("business_flow")
        rows.append({
            "id": f"BRK-{idx}",
            "source": source,
            "source_id": source_id or f"source-{idx}",
            "summary": clean,
            "business_goal": clean,
            "behavior_change": clean,
            "impact_areas": impact or ["behavior"],
            "field_impact": "confirm fields touched by this slice" if "data" in impact else "no field change confirmed",
            "api_impact": "confirm existing route or contract for this slice" if "api" in impact or "business_flow" in impact else "no API change confirmed",
            "permission_impact": "preserve existing permission; add negative case if role/data scope changes" if "permission" in impact else "preserve existing permission boundary",
        })

    acceptance = [item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]
    if len(acceptance) >= 2:
        for item in acceptance:
            add_row(
                str(item.get("criteria") or item.get("summary") or ""),
                "spec.acceptance_criteria",
                str(item.get("id") or ""),
            )
    if not rows:
        for item in as_list(spec.get("requirements")):
            if isinstance(item, dict):
                add_row(str(item.get("summary") or item.get("description") or ""), "spec.requirements", str(item.get("id") or ""))
    if not rows:
        for item in as_list(spec.get("business_rules")):
            if isinstance(item, dict):
                add_row(str(item.get("rule") or item.get("summary") or ""), "spec.business_rules", str(item.get("id") or ""))
    if not rows:
        for line in actionable_lines(spec):
            add_row(line, "spec.source_trace")
    if not rows:
        summary = str(spec.get("requirement_summary") or spec.get("title") or "Implement normalized requirement")
        add_row(summary, "spec.summary", "REQ-1")
    return rows[:12]


def tokenize_requirement(text: str) -> set[str]:
    tokens = {item.lower() for item in re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text)}
    for key, values in DOMAIN_HINTS.items():
        if any(value in text or value.lower() in tokens for value in values):
            tokens.add(key)
            tokens.update(value.lower() for value in values if re.match(r"^[A-Za-z]", value))
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        tokens.add(chunk)
        for _, values in DOMAIN_HINTS.items():
            if any(value in chunk for value in values if re.search(r"[\u4e00-\u9fff]", value)):
                tokens.update(value.lower() for value in values if re.match(r"^[A-Za-z]", value))
    return tokens


def is_generic_entrypoint(path: str) -> bool:
    low = path.lower()
    name = Path(low).name
    parts = set(Path(low).parts)
    return name in GENERIC_ENTRYPOINT_NAMES or bool(parts & GENERIC_ENTRYPOINT_PARTS)


def is_executable_test_hint(value: str) -> bool:
    stripped = value.strip()
    if not stripped:
        return False
    prefixes = ("npm ", "pnpm ", "yarn ", "pytest", "python", "mvn ", "./mvnw", "gradle", "./gradlew", "go test", "cargo ", "make ")
    return stripped.startswith(prefixes)


def is_business_route(route: dict[str, Any]) -> bool:
    route_path = str(route.get("route") or "").strip()
    file = str(route.get("file") or "").strip()
    if not route_path or route_path in {"/", "*"}:
        return False
    if is_generic_entrypoint(file):
        return False
    lower_file = file.lower()
    if lower_file.endswith((".md", ".json", ".yml", ".yaml", ".config.js", ".config.ts", "package.json", "package-lock.json")):
        return False
    return True


def route_ref(route: dict[str, Any]) -> str:
    return f"{route.get('method', '')} {route.get('route', '')} ({route.get('file', '')})".strip()


def route_relevance_score(route: dict[str, Any], subject: str) -> int:
    searchable = " ".join([
        str(route.get("method") or ""),
        str(route.get("route") or ""),
        str(route.get("file") or ""),
        str(route.get("summary") or ""),
        str(route.get("handler") or ""),
    ]).lower()
    score = 0
    for token in tokenize_requirement(subject):
        if token and token in searchable:
            score += 3
    return score


def contract_for_breakdown(route_refs: list[str], breakdown: dict[str, Any]) -> str:
    """Choose an existing contract by action semantics instead of list position."""
    if not route_refs:
        return f"{breakdown.get('id')}: no external API contract change; use confirmed owner/module boundary"
    subject = " ".join(
        str(breakdown.get(key) or "")
        for key in ["summary", "business_goal", "behavior_change"]
    ).lower()
    primary_action = re.split(r"[；;。\n]", str(breakdown.get("summary") or ""), maxsplit=1)[0].lower()
    action_families = [
        (
            ["停止", "关闭", "销毁", "清理", "结束", "stop", "close", "destroy", "cleanup", " end"],
            ["stop", "close", "destroy", "delete", "remove", "end"],
        ),
        (
            ["控制", "快进", "快退", "拖拽", "定位", "暂停", "恢复", "9202", "control", "seek", "pause", "resume", "adjust", "update"],
            ["control", "seek", "pause", "resume", "adjust", "update", "action"],
        ),
        (
            ["开始", "启动", "拉起", "起播", "9201", "start", "open", "create", "begin"],
            ["start", "open", "create", "begin"],
        ),
    ]
    for action_subject in [primary_action, subject]:
        for subject_terms, contract_terms in action_families:
            if not any(term in action_subject for term in subject_terms):
                continue
            matched = [contract for contract in route_refs if any(term in contract.lower() for term in contract_terms)]
            if matched:
                return matched[0]
    return route_refs[0]


def explicit_contract_refs_from_spec(spec: dict[str, Any]) -> list[str]:
    raw = json.dumps({
        "source_trace": spec.get("source_trace"),
        "business_rules": spec.get("business_rules"),
        "entrypoints": spec.get("entrypoints"),
        "current_business_state": spec.get("current_business_state"),
        "requirements": spec.get("requirements"),
    }, ensure_ascii=False)
    refs: list[str] = []
    for method, path in re.findall(r"\b(GET|POST|PUT|DELETE|PATCH)\s+(/[A-Za-z0-9_./{}:-]+)", raw, flags=re.I):
        ref = f"{method.upper()} {path.rstrip('`，。；;,.')}"
        if ref not in refs:
            refs.append(ref)
    for path in re.findall(r"(?<![A-Za-z0-9_])(/[A-Za-z0-9_./{}:-]+)", raw):
        clean = path.rstrip("`，。；;,.")
        if clean and not any(clean in ref for ref in refs):
            refs.append(clean)
    return refs[:10]


def parse_contract_ref(contract: str) -> dict[str, Any]:
    match = re.match(r"^\s*(?:(?P<method>[A-Z]+)\s+)?(?P<route>[^()\s]+)(?:\s+\((?P<file>[^)]+)\))?", contract)
    if not match:
        return {"contract": contract, "confirmed_contract": False}
    route = (match.group("route") or "").strip()
    file = (match.group("file") or "").strip()
    return {
        "contract": contract,
        "method": (match.group("method") or "").strip(),
        "endpoint": route if route.startswith("/") else "",
        "controller_file": "" if file == "evidence_bundle.json" else file,
        "source_evidence": file or "evidence_bundle.contracts",
        "confirmed_contract": bool(route and not contract.endswith("use confirmed owner/module boundary")),
    }


def api_contract_for_breakdown(route_refs: list[str], breakdown: dict[str, Any]) -> dict[str, Any]:
    contract = contract_for_breakdown(route_refs, breakdown)
    parsed = parse_contract_ref(contract)
    return {
        **parsed,
        "compatibility": "preserve existing consumers unless design updates contract",
        "old_consumer_impact": "review route consumers before implementation",
        "requirement_breakdown_id": breakdown.get("id"),
        "api_impact": breakdown.get("api_impact"),
        "binding_rule": "contract must come from api_surface routes or source_location evidence; guessed endpoint names are not implementation-ready",
    }


def extract_source_literals(spec: dict[str, Any]) -> list[dict[str, Any]]:
    blob = json.dumps(
        {
            "title": spec.get("title"),
            "summary": spec.get("requirement_summary"),
            "requirements": spec.get("requirements"),
            "acceptance": spec.get("acceptance_criteria"),
            "business_rules": spec.get("business_rules"),
            "source_trace": spec.get("source_trace"),
            "source": spec.get("source"),
            "data_fields": spec.get("data_fields"),
            "business_objects": spec.get("business_objects"),
        },
        ensure_ascii=False,
    )
    candidates = set(re.findall(r"/[A-Za-z0-9_./{}:-]+", blob))
    candidates.update(re.findall(r"\b[A-Z][A-Z0-9_]{2,}\b", blob))
    candidates.update(re.findall(r"\b[A-Za-z][A-Za-z0-9]*(?:[._-][A-Za-z0-9]+)+\b", blob))
    candidates.update(re.findall(r"\b\d+\s*(?:天|日|day|days|小时|hour|hours)\b", blob, flags=re.I))
    result: list[dict[str, Any]] = []
    for literal in sorted(candidates):
        clean = literal.strip(".,;:，。；：)）]】\"'")
        if len(clean) < 2 or clean.lower() in {"api", "req", "rule"}:
            continue
        result.append({"literal": clean, "source": "spec.source", "required_binding": True})
    return result[:80]


def constraint_values(spec: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    for key in keys:
        for item in as_list(spec.get(key)):
            if isinstance(item, dict):
                value = item.get("pattern") or item.get("value") or item.get("path") or item.get("contract") or item.get("behavior") or item.get("summary") or item.get("name")
                if value:
                    values.append(str(value))
            elif item:
                values.append(str(item))
    return [value for value in values if value.strip()]


def generic_constraint_model(spec: dict[str, Any]) -> dict[str, Any]:
    scope = spec.get("scope") if isinstance(spec.get("scope"), dict) else {}
    scope_model = spec.get("scope_model") if isinstance(spec.get("scope_model"), dict) else {}
    out_of_scope = [str(item) for item in as_list(scope.get("out_of_scope")) + as_list(scope.get("non_goals")) if str(item).strip()]
    out_of_scope.extend(str(item) for item in as_list(scope_model.get("out_of_scope")) if str(item).strip())
    forbidden = {
        "forbidden_reuse_paths": constraint_values(spec, "forbidden_reuse_paths", "forbidden_paths"),
        "forbidden_modules": constraint_values(spec, "forbidden_modules"),
        "forbidden_contracts": constraint_values(spec, "forbidden_contracts"),
        "forbidden_behaviors": constraint_values(spec, "forbidden_behaviors"),
        "out_of_scope_patterns": constraint_values(spec, "out_of_scope_patterns") + out_of_scope,
    }
    return {
        "schema": "codex-generic-constraint-model-v1",
        "source": "spec",
        **forbidden,
        "has_constraints": any(values for values in forbidden.values()),
        "rule": "These constraints are requirement-provided guardrails. Generic skills only propagate and validate them; they do not define domain-specific business rules.",
    }


def rank_files_for_subject(subject: str, ctx: dict[str, Any]) -> list[dict[str, Any]]:
    tokens = tokenize_requirement(subject)
    candidates: list[dict[str, Any]] = []
    file_items = [item for item in as_list(ctx.get("file_items")) if isinstance(item, dict)]
    if not file_items:
        file_items = [{"path": path} for path in as_list(ctx.get("files"))]
    entrypoints = set(str(item) for item in as_list(ctx.get("entrypoints")))
    route_files = {str(item.get("file")) for item in as_list(ctx.get("routes")) if isinstance(item, dict) and item.get("file") and is_business_route(item)}
    for item in file_items:
        path = str(item.get("path") or "")
        if not path:
            continue
        low = path.lower()
        searchable = " ".join([path, str(item.get("symbols") or ""), str(item.get("routes") or ""), str(item.get("summary") or "")]).lower()
        score = 0
        evidence: list[str] = []
        for token in tokens:
            if token and token in searchable:
                score += 6 if token in low else 3
                evidence.append(token)
        if path in entrypoints:
            score += 2
            evidence.append("repo_entrypoint")
        if path in route_files:
            score += 4
            evidence.append("route_file")
        if low.endswith((".vue", ".tsx", ".jsx")) and any(token in subject for token in ["页面", "按钮", "表格", "筛选", "排序", "隐藏", "ui"]):
            score += 3
            evidence.append("frontend_component")
        if low.endswith((".java", ".go", ".py", ".ts", ".js")):
            score += 1
        if is_generic_entrypoint(path):
            score -= 8
            evidence.append("generic_entrypoint_penalty")
        if any(segment in low for segment in ["test", "spec", "__tests__"]):
            score -= 2
        if score > -6:
            candidates.append({"path": path, "score": score, "evidence": sorted(set(evidence)), "generic": is_generic_entrypoint(path)})
    return sorted(candidates, key=lambda item: (item["score"], not item["generic"], item["path"]), reverse=True)


def select_owner_file(summary: str, breakdown: list[dict[str, Any]], ctx: dict[str, Any], fallback: str) -> tuple[str, dict[str, Any]]:
    location_evidence = ctx.get("source_location_evidence") if isinstance(ctx.get("source_location_evidence"), dict) else {}
    confirmed = [item for item in as_list(location_evidence.get("confirmed_anchors")) if isinstance(item, dict) and item.get("path") and item.get("role", "modify_candidate") != "reference_only"]
    rejected = [str(item.get("path")) for item in as_list(location_evidence.get("rejected_candidates")) if isinstance(item, dict) and item.get("path")]
    if confirmed:
        selected = confirmed[0]
        return str(selected["path"]), {
            "level": str(selected.get("confidence") or "high"),
            "selected_entrypoint": str(selected["path"]),
            "score": int(selected.get("index_score") or 0),
            "evidence": ["direct_source_confirmation", *[str(item.get("term")) for item in as_list(selected.get("evidence_chain")) if isinstance(item, dict) and item.get("term")]],
            "ranked_candidates": confirmed[:8],
            "confirmed_anchors": [str(item.get("path")) for item in confirmed],
            "rejected_candidates": rejected,
            "source_location_decision": location_evidence.get("decision"),
            "source_digest": selected.get("source_digest"),
        }
    if location_evidence:
        return fallback, {
            "level": "low",
            "selected_entrypoint": fallback,
            "score": 0,
            "evidence": ["source_location_evidence_blocked"],
            "ranked_candidates": [],
            "confirmed_anchors": [],
            "rejected_candidates": rejected,
            "source_location_decision": location_evidence.get("decision") or "block",
            "blocker": "no requirement-specific source location was confirmed; do not infer an owner from the broad repository index",
        }
    subject = " ".join([summary, " ".join(str(item.get("summary")) for item in breakdown)])
    ranked = rank_files_for_subject(subject, ctx)
    if ranked and ranked[0]["score"] >= 4 and not ranked[0]["generic"]:
        level = "high" if ranked[0]["score"] >= 10 else "medium"
        return ranked[0]["path"], {"level": level, "selected_entrypoint": ranked[0]["path"], "score": ranked[0]["score"], "evidence": ranked[0]["evidence"], "ranked_candidates": ranked[:8]}
    non_generic = next((item for item in ranked if not item["generic"] and item["score"] >= 1), None)
    if non_generic:
        return non_generic["path"], {"level": "medium", "selected_entrypoint": non_generic["path"], "score": non_generic["score"], "evidence": non_generic["evidence"], "ranked_candidates": ranked[:8]}
    selected = ranked[0]["path"] if ranked else fallback
    return selected, {"level": "low", "selected_entrypoint": selected, "score": ranked[0]["score"] if ranked else 0, "evidence": ranked[0]["evidence"] if ranked else ["no_code_index_match"], "ranked_candidates": ranked[:8], "blocker": "primary code entrypoint is generic or weakly matched; inspect project manually before implementation"}


def impact_set(spec: dict[str, Any], breakdown: list[dict[str, Any]]) -> set[str]:
    impacts = {str(item.get("area")) for item in as_list(spec.get("impact_surface")) if isinstance(item, dict) and item.get("area")}
    for item in breakdown:
        impacts.update(str(value) for value in as_list(item.get("impact_areas")))
    return {item for item in impacts if item}


def option_score_summary(options: list[dict[str, Any]], matrix: list[dict[str, Any]]) -> dict[str, Any]:
    scores = {str(option["option_id"]): 0 for option in options if option.get("option_id")}
    for row in matrix:
        weight = int(row.get("weight") or 1)
        for option_id, score in (row.get("scores") or {}).items():
            if option_id in scores:
                scores[option_id] += weight * int(score)
    max_score = max(scores.values()) if scores else 1
    normalized = {key: round(value * 100 / max_score) for key, value in scores.items()}
    normalized["scoring_rule"] = "Scores are weighted from requirement-specific criteria; selected option should match the highest total unless the design records an explicit exception."
    return normalized


def selected_from_scores(score_summary: dict[str, Any]) -> str:
    numeric = {key: value for key, value in score_summary.items() if key != "scoring_rule" and isinstance(value, int | float)}
    return max(numeric, key=numeric.get) if numeric else ""


def option_name(option_id: str, owner_file: str, primary_slice: str, impacts: set[str], route_refs: list[str]) -> str:
    if option_id == "T1":
        if "ui" in impacts:
            return f"在现有页面/组件 `{owner_file}` 内完成「{primary_slice[:28]}」"
        return f"在现有责任模块 `{owner_file}` 内完成「{primary_slice[:28]}」"
    if option_id == "T2":
        if route_refs or "api" in impacts:
            return "通过既有接口/服务契约承接业务规则"
        if "ui" in impacts:
            return "仅调整前端展示与交互状态"
        return "抽取共享业务规则后再接入现有流程"
    if option_id == "T3":
        return "先明确字段、默认值和历史数据口径"
    return option_id


def selected_option_reason(selected_id: str, owner_file: str, primary_slice: str, options: list[dict[str, Any]]) -> str:
    selected = next((item for item in options if item.get("option_id") == selected_id), {})
    selected_name = str(selected.get("name") or selected_id)
    if selected_id == "T1":
        return (
            f"选择 {selected_id}（{selected_name}），因为当前证据显示 `{owner_file}` 是最清晰的责任入口，"
            f"「{primary_slice}」可以在现有模块边界内闭环，不需要先扩大接口、数据模型或跨仓契约。"
            "该选择的测试路径最短，回滚也可以控制在责任模块和对应发布制品内。"
        )
    if selected_id == "T2":
        return (
            f"选择 {selected_id}（{selected_name}），因为当前需求的正确性取决于接口/服务契约，"
            "需要先让生产方与消费方对请求、响应、兼容行为形成一致口径，再进入页面或调用方改造。"
        )
    if selected_id == "T3":
        return (
            f"选择 {selected_id}（{selected_name}），因为当前需求依赖字段语义、默认值或历史数据处理，"
            "必须先把数据口径和迁移/无需迁移证据说明清楚，再做业务行为变更。"
        )
    if "权限" in selected_name:
        return (
            f"选择 {selected_id}（{selected_name}），因为当前需求的验收风险集中在角色、租户、数据范围或操作权限，"
            "需要把前端可见性、服务端鉴权和反向权限证据放在同一方案内闭环。"
        )
    if "前后端分层" in selected_name:
        return (
            f"选择 {selected_id}（{selected_name}），因为当前验收同时影响页面交互、接口语义和数据口径，"
            "需要先冻结契约和查询口径，再让前端按稳定返回完成展示与状态处理。"
        )
    if "子域" in selected_name:
        return (
            f"选择 {selected_id}（{selected_name}），因为当前需求包含多个业务切片且影响面不同，"
            "按子域拆分能让字段、接口、权限、批量流程和回滚证据分别评审，避免把复杂需求压进单一入口后难以验收和定位。"
        )
    return f"选择 {selected_id}（{selected_name}），因为它最符合当前需求证据和交付约束。"


def rejected_option_reason(option: dict[str, Any], selected_score: Any, option_score: Any) -> str:
    option_id = str(option.get("option_id"))
    name = str(option.get("name") or option_id)
    if "接口" in name or "契约" in name or "共享业务规则" in name:
        return (
            f"暂不选择 {option_id}（{name}）：当前证据还不足以证明必须调整接口/服务契约或抽取共享规则；"
            "若代码检查发现多个入口复用同一规则、现有模块会重复校验，或接口响应缺少必要字段，再切换到该方案。"
            f"本轮评分 {option_score}，低于选中方案 {selected_score}。"
        )
    if "字段" in name or "数据" in name:
        return (
            f"暂不选择 {option_id}（{name}）：当前证据还不足以证明需要先处理字段语义、历史数据或迁移边界；"
            "若实现前发现空值、历史记录、筛选口径或回滚数据风险会影响验收，再切换到该方案。"
            f"本轮评分 {option_score}，低于选中方案 {selected_score}。"
        )
    if "权限" in name:
        return (
            f"暂不选择 {option_id}（{name}）：当前证据还不足以证明权限链路是主导风险；"
            "若实现前发现前端可见性、后端鉴权或角色数据范围会影响验收，再切换到该方案。"
            f"本轮评分 {option_score}，低于选中方案 {selected_score}。"
        )
    if "子域" in name:
        return (
            f"暂不选择 {option_id}（{name}）：当前证据下仍可先以主责任入口推进；"
            "若子需求之间的责任文件、接口、数据或回滚边界明显不同，再切换为子域拆分方案。"
            f"本轮评分 {option_score}，低于选中方案 {selected_score}。"
        )
    return f"暂不选择 {option_id}（{name}）：相对选中方案，当前证据下交付边界、测试或回滚成本更高。本轮评分 {option_score}，低于选中方案 {selected_score}。"


def next_option_id(options: list[dict[str, Any]]) -> str:
    return f"T{len(options) + 1}"


def option_ids_matching(options: list[dict[str, Any]], *needles: str) -> set[str]:
    matched: set[str] = set()
    for option in options:
        option_id = str(option.get("option_id") or "")
        name = str(option.get("name") or "")
        if option_id and any(needle in name for needle in needles):
            matched.add(option_id)
    return matched


def winner_from_scores(scores: dict[str, int]) -> str:
    return max(scores, key=scores.get) if scores else ""


def build_problem_analysis(
    spec: dict[str, Any],
    ctx: dict[str, Any],
    summary: str,
    breakdown: list[dict[str, Any]],
    owner_file: str,
    read_first: list[str],
    route_refs: list[str],
    entrypoint_confidence: dict[str, Any],
) -> dict[str, Any]:
    impacts = sorted(impact_set(spec, breakdown))
    acceptance = [
        re.sub(r"^User-visible behavior matches:\s*", "", str(item.get("criteria") or item.get("summary")).strip())
        for item in as_list(spec.get("acceptance_criteria"))
        if isinstance(item, dict) and str(item.get("criteria") or item.get("summary") or "").strip() not in {"", "标准", "验收"}
    ]
    rules = [str(item.get("rule") or item.get("summary")) for item in as_list(spec.get("business_rules")) if isinstance(item, dict)]
    slice_summaries = [str(item.get("summary")) for item in breakdown[:6] if item.get("summary")]
    current_behavior = f"{ctx['project']} 当前应从 `{owner_file}` 进入分析，入口置信度为 {entrypoint_confidence.get('level')}；关联候选包括 {', '.join(read_first[:4])}。"
    business_problem = "; ".join(slice_summaries[:3]) or summary
    process_gap = f"现有流程需要逐项核对 {len(breakdown)} 个业务切片：{', '.join(slice_summaries[:4])}。"
    constraint_parts = []
    concrete_routes = [route for route in route_refs if not route.startswith("/ (")]
    if concrete_routes:
        constraint_parts.append(f"接口/契约面：{concrete_routes[0]}")
    if "permission" in impacts:
        constraint_parts.append("权限边界必须有反向用例证据")
    if "data" in impacts:
        constraint_parts.append("字段读写、默认值或历史数据语义必须明确")
    if "ui" in impacts:
        constraint_parts.append("页面状态、筛选、展示或折叠规则必须验证")
    if not constraint_parts:
        constraint_parts.append("保持现有契约、校验和权限行为")
    return {
        "current_behavior": current_behavior,
        "business_problem": business_problem,
        "process_gap": process_gap,
        "code_entrypoints": read_first,
        "constraints": constraint_parts,
        "design_goals": acceptance[:5] or slice_summaries[:5] or [summary],
        "non_goals": as_list((spec.get("scope") or {}).get("non_goals")) or as_list((spec.get("scope") or {}).get("out_of_scope")),
        "success_criteria": acceptance[:6] or [f"验收证据证明：{summary}"],
        "source_rules": rules[:6],
        "impact_areas": impacts or ["behavior"],
    }


def build_current_state_analysis(problem: dict[str, Any], owner_module: str, route_refs: list[str]) -> dict[str, Any]:
    return {
        "existing_behavior": problem["current_behavior"],
        "business_problem": problem["business_problem"],
        "process_gap": problem["process_gap"],
        "code_entrypoints": problem["code_entrypoints"],
        "known_constraints": problem["constraints"],
        "reuse_points": [owner_module, *(route_refs[:2] or [])],
        "design_goals": problem["design_goals"],
        "non_goals": problem["non_goals"],
        "success_criteria": problem["success_criteria"],
    }


def build_technical_options(
    spec: dict[str, Any],
    summary: str,
    owner_file: str,
    breakdown: list[dict[str, Any]],
    route_refs: list[str],
    test_evidence: list[str],
    problem: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    impacts = set(problem.get("impact_areas") or [])
    complexity_count = max(len(breakdown), len([item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]))
    primary_slice = str(breakdown[0].get("summary") if breakdown else summary)
    options: list[dict[str, Any]] = [
        {
            "option_id": "T1",
            "name": option_name("T1", owner_file, primary_slice, impacts, route_refs),
            "description": f"围绕 `{owner_file}` 这个已识别责任入口实现本次行为变化，并把 {len(breakdown)} 个业务切片逐一绑定到验收证据。",
            "when_to_choose": [f"`{owner_file}` 仍是最可信的责任入口", "验收目标可以在不修改外部契约的情况下完成"],
            "implementation_outline": [f"先阅读 `{owner_file}` 及相邻测试", f"逐项实现业务切片：{', '.join(str(item.get('id')) for item in breakdown[:5])}", "保持既有校验、权限和兼容路径不变"],
            "pros": ["责任入口清晰，改动边界收敛", "实现与现有行为距离最近，便于评审和回滚"],
            "cons": ["多个业务切片可能集中在同一模块", "如果后续多个流程复用同一规则，扩展性弱于抽象方案"],
            "risk_level": "low" if len(breakdown) <= 3 else "medium",
            "risk_controls": ["bind allowed_files to selected entrypoints", "map every acceptance criterion to evidence", "re-run design review if inspection finds a different owner"],
            "validation": f"Run mapped tests for {owner_file} and acceptance evidence",
            "test_evidence": test_evidence,
            "performance_impact": "bounded to existing flow unless data/API slice adds extra queries or calls",
            "rollout_impact": "single owner module rollout",
            "rollback_strategy": f"revert changes in `{owner_file}` and redeploy previous artifact",
        }
    ]
    if {"api", "business_flow"} & impacts or route_refs:
        options.append({
            "option_id": "T2",
            "name": option_name("T2", owner_file, primary_slice, impacts, route_refs),
            "description": f"先确认 `{route_refs[0] if route_refs else '相关接口/服务'}` 是否才是「{primary_slice[:32]}」的事实来源，再决定页面或调用方如何接入。",
            "when_to_choose": ["接口/服务契约持有核心业务规则", "多个调用方或页面依赖同一结果"],
            "implementation_outline": [f"确认契约 `{route_refs[0] if route_refs else 'mapped route/service'}`", "补充向后兼容的请求/响应处理", "用契约证据覆盖新旧消费方行为"],
            "pros": ["业务规则留在契约责任方", "减少前端或调用方重复实现逻辑"],
            "cons": ["需要消费方兼容性评审", "集成测试面更大"],
            "risk_level": "medium",
            "risk_controls": ["contract compatibility matrix", "old-consumer regression evidence", "ordered rollback if provider and consumer both change"],
            "validation": "contract, integration, and regression evidence",
            "test_evidence": ["contract test evidence", "integration evidence", *test_evidence],
            "performance_impact": "review route/query latency and payload growth",
            "rollout_impact": "may require provider/consumer coordination",
            "rollback_strategy": "rollback consumers before provider if a contract change is deployed",
        })
    elif "ui" in impacts:
        options.append({
            "option_id": "T2",
            "name": option_name("T2", owner_file, primary_slice, impacts, route_refs),
            "description": f"保持数据和接口行为稳定，仅通过页面/组件状态、展示规则或交互默认值满足「{primary_slice[:32]}」。",
            "when_to_choose": ["验收目标主要体现在页面或组件层", "现有接口已经提供必要数据"],
            "implementation_outline": ["将页面状态绑定到现有数据", "补充加载、空态、错误态和权限可见性", "采集受影响角色的浏览器验收证据"],
            "pros": ["不改变后端契约", "回滚可通过前端制品快速完成"],
            "cons": ["无法修复后端缺失数据", "必须避免在前端重复服务端权威规则"],
            "risk_level": "low",
            "risk_controls": ["browser acceptance evidence", "permission visibility negative case", "no client-side authority for security rules"],
            "validation": "browser and component evidence",
            "test_evidence": ["browser evidence", *test_evidence],
            "performance_impact": "limited to rendering unless additional client filtering is introduced",
            "rollout_impact": "frontend artifact rollout",
            "rollback_strategy": "revert frontend component change",
        })
    else:
        options.append({
            "option_id": "T2",
            "name": option_name("T2", owner_file, primary_slice, impacts, route_refs),
            "description": f"先把「{primary_slice[:32]}」背后的规则抽成可复用 helper/service，再让责任流程接入该规则。",
            "when_to_choose": ["同一规则出现在多个业务切片或流程中", "继续放在责任模块内会产生重复校验或重复计算"],
            "implementation_outline": ["识别重复规则边界", "抽取 helper/service 并补充测试", "更新责任流程使用共享规则"],
            "pros": ["复用点更清晰", "后续重复变更成本更低"],
            "cons": ["重构面更大", "需要更强的回归覆盖"],
            "risk_level": "medium",
            "risk_controls": ["focused unit tests for extracted rule", "regression evidence for old flow", "rollback plan covering helper and caller"],
            "validation": "unit and regression evidence",
            "test_evidence": ["rule unit test evidence", "regression evidence", *test_evidence],
            "performance_impact": "no new IO expected; verify no extra query/call is introduced",
            "rollout_impact": "owner artifact rollout with changed internal boundary",
            "rollback_strategy": "revert helper extraction and caller change together",
        })
    if "data" in impacts:
        options.append({
            "option_id": next_option_id(options),
            "name": "先明确字段、默认值和历史数据口径",
            "description": "在行为变更依赖数据结构前，先明确字段含义、默认值、读写规则、历史数据和回滚边界。",
            "when_to_choose": ["新增或变更字段属于验收内容", "历史记录、空值或默认值会影响正确性"],
            "implementation_outline": ["定义字段语义和是否需要迁移/回填", "围绕变更字段补充读写保护", "覆盖新旧数据形态测试"],
            "pros": ["降低隐藏的数据兼容风险", "迁移和回滚边界更清楚"],
            "cons": ["若涉及结构变化，需要迁移/回填证据", "可能需要发布顺序控制"],
            "risk_level": "medium",
            "risk_controls": ["migration plan or explicit no-migration proof", "old-data regression evidence", "rollback data-risk review"],
            "validation": "data compatibility and regression evidence",
            "test_evidence": ["old-data regression evidence", "migration/no-migration evidence", *test_evidence],
            "performance_impact": "review added query/filter/index cost",
            "rollout_impact": "may require data/config release step",
            "rollback_strategy": "rollback code first; handle data according to migration strategy",
        })
    if "permission" in impacts or "权限测试" in impacts:
        options.append({
            "option_id": next_option_id(options),
            "name": "前后端权限一致性方案",
            "description": "把入口可见性、按钮/菜单权限、后端鉴权和反向权限用例作为一个独立方案处理，避免只在前端隐藏入口。",
            "when_to_choose": ["需求涉及角色、租户、数据范围或操作权限", "未授权用户的负向验收必须成立"],
            "implementation_outline": ["确认权限来源和角色边界", "前端只做可见性和交互限制", "后端或接口侧保留权威校验并补充负向测试"],
            "pros": ["越权风险可控", "前后端权限语义一致"],
            "cons": ["需要权限账号和负向数据准备", "可能需要补充接口鉴权证据"],
            "risk_level": "medium",
            "risk_controls": ["permission negative evidence", "role/data-scope fixture", "server-side authorization confirmation"],
            "validation": "permission positive and negative evidence",
            "test_evidence": ["permission test evidence", *test_evidence],
            "performance_impact": "no material performance impact unless permission lookup changes",
            "rollout_impact": "may require role/account fixture verification before release",
            "rollback_strategy": "revert permission visibility and authorization changes together",
        })
    if "ui" in impacts and ({"api", "business_flow", "data"} & impacts):
        options.append({
            "option_id": next_option_id(options),
            "name": "前后端分层协同方案",
            "description": "将页面交互、接口参数/响应、数据口径分别落在各自责任层，按契约先行、页面随后适配的顺序推进。",
            "when_to_choose": ["同一验收同时影响页面展示、查询条件和业务流程", "单纯页面内修改无法证明数据或接口口径正确"],
            "implementation_outline": ["先冻结接口或查询口径", "后端返回稳定字段和错误语义", "前端按新契约完成展示、筛选和状态处理"],
            "pros": ["层次边界清晰", "能覆盖复杂页面和接口联动"],
            "cons": ["协同和集成测试成本高于单模块方案", "发布顺序需要更谨慎"],
            "risk_level": "medium",
            "risk_controls": ["contract compatibility evidence", "browser acceptance evidence", "integration regression evidence"],
            "validation": "contract, browser, and integration evidence",
            "test_evidence": ["contract test evidence", "frontend_acceptance.json", "integration evidence", *test_evidence],
            "performance_impact": "review query/filter and render cost together",
            "rollout_impact": "may require backend-compatible release before frontend rollout",
            "rollback_strategy": "rollback frontend first, then backend contract change if compatibility fails",
        })
    complex_multi_surface = complexity_count >= 5 and len(impacts & {"ui", "api", "data", "permission", "business_flow"}) >= 3
    if complex_multi_surface:
        options.append({
            "option_id": next_option_id(options),
            "name": "按业务子域拆分交付方案",
            "description": f"将 {complexity_count} 个业务切片/验收点按页面展示、查询筛选、批量操作、字段口径、权限校验等子域拆分设计和验证。",
            "when_to_choose": ["需求包含多个业务子项且影响面不同", "一个 owner 模块内整体改造会让评审、测试或回滚边界不清晰"],
            "implementation_outline": ["对子需求分组并绑定责任文件/接口", "每个子域独立给出验收和测试证据", "按低风险子域到高风险子域组织提交和回滚"],
            "pros": ["复杂需求更容易评审", "测试和回滚可以按子域定位"],
            "cons": ["计划和证据维护成本更高", "需要更明确的子需求优先级"],
            "risk_level": "medium",
            "risk_controls": ["subdomain traceability matrix", "per-domain acceptance evidence", "per-domain rollback note"],
            "validation": "per-subdomain functional and regression evidence",
            "test_evidence": ["subdomain acceptance evidence", "regression evidence", *test_evidence],
            "performance_impact": "review each subdomain independently",
            "rollout_impact": "can be staged by subdomain when release policy allows",
            "rollback_strategy": "rollback by subdomain or revert the whole requirement branch if cross-domain coupling is high",
        })
    option_ids = [str(option["option_id"]) for option in options]
    contract_option_ids = option_ids_matching(options, "接口", "契约", "共享业务规则")
    data_option_ids = option_ids_matching(options, "字段", "数据")
    permission_option_ids = option_ids_matching(options, "权限")
    layered_option_ids = option_ids_matching(options, "前后端分层")
    subdomain_option_ids = option_ids_matching(options, "子域")
    high_risk_impacts = impacts & {"ui", "api", "data", "permission", "business_flow"}
    complex_multi_surface = complexity_count >= 5 and len(high_risk_impacts) >= 3
    matrix: list[dict[str, Any]] = []

    scores = {
        oid: (
            5 if oid in subdomain_option_ids and complex_multi_surface else
            4 if oid == "T1" and complex_multi_surface else
            5 if oid == "T1" else
            4 if oid in subdomain_option_ids else
            3
        )
        for oid in option_ids
    }
    matrix.append({"criterion": "验收适配度", "weight": 5, "scores": scores, "winner": winner_from_scores(scores), "reason": f"T1 可以把 {len(breakdown)} 个业务切片直接落到 `{owner_file}` 的责任边界内；复杂多子域需求则需要拆分方案补强。"})

    scores = {
        oid: (
            5 if oid in contract_option_ids and (route_refs or "api" in impacts or "business_flow" in impacts) else
            4 if oid == "T1" and "api" not in impacts else
            3
        )
        for oid in option_ids
    }
    matrix.append({"criterion": "契约安全性", "weight": 4, "scores": scores, "winner": winner_from_scores(scores), "reason": "接口/服务行为是事实来源时，契约方案优先；否则责任模块内闭环的兼容风险更低。"})

    scores = {
        oid: (
            5 if oid in data_option_ids and "data" in impacts else
            4 if oid == "T1" else
            3
        )
        for oid in option_ids
    }
    matrix.append({"criterion": "数据正确性", "weight": 4, "scores": scores, "winner": winner_from_scores(scores), "reason": "字段、默认值、历史数据或迁移语义主导正确性时，数据口径方案优先。"})

    if permission_option_ids:
        scores = {oid: (5 if oid in permission_option_ids else 4 if oid == "T1" else 3) for oid in option_ids}
        matrix.append({"criterion": "越权风险控制", "weight": 5, "scores": scores, "winner": winner_from_scores(scores), "reason": "需求涉及角色、租户、菜单、按钮或数据范围时，必须显式比较前端可见性与后端鉴权闭环。"})

    if layered_option_ids:
        scores = {oid: (5 if oid in layered_option_ids else 4 if oid in contract_option_ids else 3 if complex_multi_surface else 4 if oid == "T1" else 3) for oid in option_ids}
        matrix.append({"criterion": "前后端协同清晰度", "weight": 4, "scores": scores, "winner": winner_from_scores(scores), "reason": "同一验收跨页面、接口、数据或流程时，需要比较各层责任、集成顺序和契约冻结点。"})

    if subdomain_option_ids:
        scores = {oid: (5 if oid in subdomain_option_ids else 3 if oid == "T1" and complex_multi_surface else 4 if oid == "T1" else 3) for oid in option_ids}
        matrix.append({"criterion": "子域可拆分性", "weight": 5 if complex_multi_surface else 4, "scores": scores, "winner": winner_from_scores(scores), "reason": "业务切片较多时，需要显式比较按子域设计、测试、发布和回滚的可控性。"})

    scores = {
        oid: (
            5 if oid in subdomain_option_ids and complex_multi_surface else
            4 if oid == "T1" and complex_multi_surface else
            5 if oid == "T1" else
            4 if oid in subdomain_option_ids else
            3
        )
        for oid in option_ids
    }
    matrix.append({"criterion": "测试可证明性", "weight": 4, "scores": scores, "winner": winner_from_scores(scores), "reason": f"`{owner_file}` 的证据链最短；复杂需求可通过子域级证据降低证明难度。"})

    scores = {oid: (5 if oid == "T1" and not complex_multi_surface else 4 if oid == "T1" else 4 if oid in permission_option_ids and "permission" in impacts else 4 if oid in subdomain_option_ids and complex_multi_surface else 3) for oid in option_ids}
    matrix.append({"criterion": "回滚可控性", "weight": 3, "scores": scores, "winner": winner_from_scores(scores), "reason": "责任模块内变更的依赖链最短；权限方案需要前后端权限改动一起回退。"})
    summary_scores = option_score_summary(options, matrix)
    selected_id = selected_from_scores(summary_scores)
    selected = {
        "selected_option_id": selected_id,
        "selection_reason": selected_option_reason(selected_id, owner_file, primary_slice, options),
        "decision_criteria": [str(row["criterion"]) for row in matrix],
        "tradeoffs": [f"接受的取舍：{next((option['cons'][0] for option in options if option['option_id'] == selected_id), '实现风险需要持续监控')}", "如果代码检查推翻责任入口、契约边界或数据口径假设，需要回到候选方案重新评审"],
        "rejected_alternative_reasoning": [
            {"option_id": option["option_id"], "reason": rejected_option_reason(option, summary_scores.get(selected_id), summary_scores.get(option["option_id"]))}
            for option in options
            if option["option_id"] != selected_id
        ],
    }
    return options, matrix, summary_scores, selected


def load_project_understanding(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    base = path if path.is_dir() else path.parent
    if not base.exists():
        return {}
    result: dict[str, Any] = {}
    bundle_file = base / "evidence_bundle.json"
    if bundle_file.exists():
        result["evidence_bundle"] = load_json(bundle_file)
        for name in ["repository_analysis", "api_surface", "config_surface", "dependency_surface", "code_index", "source_location_evidence"]:
            file = base / f"{name}.json"
            if file.exists():
                result[name] = load_json(file)
        return result
    for name in ["repository_analysis", "api_surface", "config_surface", "dependency_surface", "code_index", "source_location_evidence", "baseline", "baseline_quality"]:
        file = base / f"{name}.json"
        if file.exists():
            result[name] = load_json(file)
    return result


def project_context(project_understanding: dict[str, Any]) -> dict[str, Any]:
    bundle = project_understanding.get("evidence_bundle", {})
    repo = project_understanding.get("repository_analysis", {})
    api = project_understanding.get("api_surface", {})
    config = project_understanding.get("config_surface", {})
    deps = project_understanding.get("dependency_surface", {})
    index = project_understanding.get("code_index", {})
    baseline = project_understanding.get("baseline", {})
    source_locations = project_understanding.get("source_location_evidence", {})
    if bundle:
        merged_source_locations = dict(source_locations) if isinstance(source_locations, dict) else {}
        for key, value in bundle.items():
            merged_source_locations.setdefault(key, value)
        source_locations = merged_source_locations
    project = str(bundle.get("project") or repo.get("project") or api.get("project") or baseline.get("project") or "target-repo")
    repo_root = str(bundle.get("repo_root") or index.get("repo_root") or baseline.get("repo_root") or repo.get("repo_root") or "")
    entrypoints = [str(item) for item in as_list(repo.get("entrypoint_hints"))]
    modules = [str(item.get("module")) for item in as_list(baseline.get("module_hints")) if isinstance(item, dict) and item.get("module")]
    if not modules:
        modules = [str(item) for item in as_list(repo.get("top_level_directories"))]
    modules = [item for item in modules if item not in {".github", ".git", "tests", "__pycache__"}] or modules
    file_items = [item for item in as_list(index.get("files")) if isinstance(item, dict) and item.get("path")]
    files = [str(item.get("path")) for item in file_items]
    routes = [item for item in as_list(api.get("routes")) if isinstance(item, dict)]
    if bundle:
        anchors = [item for item in as_list(bundle.get("confirmed_anchors")) if isinstance(item, dict) and item.get("path")]
        file_items = [{"path": item["path"]} for item in anchors]
        files = [str(item["path"]) for item in anchors]
        entrypoints = [str(item["path"]) for item in anchors if item.get("role") != "reference_only"]
        modules = sorted({str(Path(item).parent) for item in files})
        routes = [{"method": "", "route": str(contract), "file": "evidence_bundle.json"} for contract in as_list(bundle.get("contracts"))]
    config_items = [item for item in as_list(config.get("config_items")) if isinstance(item, dict)]
    raw_test_hints = [str(item) for item in as_list(deps.get("test_command_hints"))] or [str(item) for item in as_list(repo.get("test_hints"))]
    test_hints = [item for item in raw_test_hints if is_executable_test_hint(item)]
    test_file_hints = [item for item in raw_test_hints if item not in test_hints]
    return {
        "project": project,
        "repo_root": repo_root,
        "local_project_binding": bundle.get("local_project_binding") if isinstance(bundle.get("local_project_binding"), dict) else {},
        "entrypoints": entrypoints,
        "modules": modules,
        "file_items": file_items,
        "files": files,
        "routes": routes,
        "config_items": config_items,
        "test_hints": test_hints,
        "test_file_hints": test_file_hints[:20],
        "framework_hints": [str(item) for item in as_list(repo.get("framework_hints"))],
        "source_location_evidence": source_locations if isinstance(source_locations, dict) else {},
    }


def render_data_model_design(signals: dict[str, bool], spec: dict[str, Any], breakdown: list[dict[str, Any]], owner_file: str) -> dict[str, Any]:
    data_fields = [str(item.get("name") or item.get("field") or item) for item in as_list(spec.get("data_fields")) if item]
    business_objects = [str(item.get("name") or item.get("object") or item) for item in as_list(spec.get("business_objects")) if item]
    applicable = bool(signals.get("data"))
    field_rules = [
        {
            "field": field,
            "type": "needs_confirmation",
            "nullable": "needs_confirmation",
            "default": "needs_confirmation",
            "meaning": field,
            "migration": "确认是否需要历史数据回填。",
        }
        for field in data_fields
    ]
    table_rows = [
        {
            "table": "needs_confirmation",
            "business_object": business_objects[0] if business_objects else str(item.get("summary") or "business object"),
            "owner_module": owner_file,
            "confirmation_required": True,
            "reason": "项目理解中未可靠提取真实表名，设计阶段不能伪造表结构。",
        }
        for item in (breakdown[:1] if applicable else [])
    ]
    return {
        "applicable": applicable,
        "reason": "需求涉及字段、状态、结算、历史数据或显式数据影响。" if applicable else "未识别到字段、表结构、状态或历史数据变更信号。",
        "not_applicable_reason": "" if applicable else "本次保持现有 API 字段和持久化结构不变，仅调整前端交互与播放器生命周期。",
        "business_objects": business_objects or [str(item.get("summary")) for item in breakdown[:3] if item.get("summary")],
        "entities": table_rows,
        "tables": table_rows,
        "field_rules": field_rules if applicable else [],
        "fields": field_rules if applicable else [],
        "ownership": f"`{owner_file}` owns code changes;真实数据 owner 和表结构需从项目理解/数据库变更中确认。" if applicable else "",
        "read_write_rules": {"read": "确认查询来源、过滤条件、空值语义和历史数据口径。", "write": "确认写入入口、默认值、幂等和权限校验。"} if applicable else {},
        "migration_strategy": "确认历史记录、空值、默认值和回填范围；无数据结构变化时记录 no-migration evidence。",
        "indexes": [{"table": "needs_confirmation", "index": "needs_confirmation", "reason": "筛选/排序/高频查询时必须评估索引。"}] if applicable else [],
        "history_data_strategy": "确认历史记录、空值、默认值和回填范围；无数据结构变化时记录 no-migration evidence。",
        "rollback_strategy": "优先回滚代码；如存在迁移/回填，必须给出反向脚本或兼容读策略。",
        "evidence_required": ["schema/no-schema decision", "migration/backfill evidence", "old-data regression evidence"] if applicable else [],
        "open_questions": ["真实表名、字段类型、索引和历史数据回填范围需从代码/数据库变更中确认。"] if applicable else [],
    }


def render_table_schema_changes(data_model: dict[str, Any]) -> list[dict[str, Any]]:
    if not data_model.get("applicable"):
        return [{"applicable": False, "reason": data_model.get("reason"), "change_type": "none"}]
    rows = []
    fields = as_list(data_model.get("fields")) or [{"field": "needs_confirmation", "meaning": "字段影响需确认"}]
    for field in fields:
        rows.append({
            "applicable": True,
            "table": "needs_confirmation",
            "field": field.get("field") if isinstance(field, dict) else str(field),
            "type": field.get("type", "needs_confirmation") if isinstance(field, dict) else "needs_confirmation",
            "nullable": field.get("nullable", "needs_confirmation") if isinstance(field, dict) else "needs_confirmation",
            "default": field.get("default", "needs_confirmation") if isinstance(field, dict) else "needs_confirmation",
            "index": "evaluate if used by filtering/sorting",
            "migration": field.get("migration", "needs_confirmation") if isinstance(field, dict) else "needs_confirmation",
            "rollback": "code rollback plus schema/data rollback plan if migration is applied",
        })
    return rows


def render_system_interaction_sequence(signals: dict[str, bool], route_refs: list[str], owner_file: str, summary: str, confirmed_modules: list[str] | None = None) -> dict[str, Any]:
    applicable = bool(signals.get("system"))
    confirmed_modules = confirmed_modules or []
    participants = ["User/Client", owner_file, *[item for item in confirmed_modules if item != owner_file]]
    external_participants: list[str] = []
    if "飞书" in summary or "feishu" in summary.lower():
        external_participants.append("Feishu Approval")
    participants.extend(external_participants)
    participants.extend(item for item in route_refs if item not in participants)
    sequence = [{"step": 1, "from": "User/Client", "to": owner_file, "mode": "sync", "action": summary, "success": "页面接受操作", "failure": "保留输入并展示错误", "state_transition": "idle -> handling", "source_evidence": "spec.entrypoints"}]
    if "Feishu Approval" in external_participants:
        sequence.append({
            "step": len(sequence) + 1,
            "from": owner_file,
            "to": "Feishu Approval",
            "mode": "sync_or_async",
            "action": "create approval instance for the configured scenario and template",
            "success": "approval instance id and pending status are persisted",
            "failure": "record creation failure reason and expose retry from the operation page",
            "state_transition": "pending_create -> pending_approval|create_failed",
            "source_evidence": "requirement.business_flow",
        })
        sequence.append({
            "step": len(sequence) + 1,
            "from": "Feishu Approval",
            "to": owner_file,
            "mode": "callback",
            "action": "send approval result callback",
            "success": "approved callback triggers one settlement order; rejected callback records rejection without order creation",
            "failure": "record callback/build-order failure and keep idempotent retry path",
            "state_transition": "pending_approval -> approved|rejected|callback_failed",
            "source_evidence": "requirement.business_flow",
        })
    for contract in route_refs:
        sequence.append({"step": len(sequence) + 1, "from": owner_file, "to": contract, "mode": "async_response", "action": f"调用或复用已确认契约 {contract}", "success": "契约返回兼容结果并只提交当前有效响应", "failure": "超时/错误时保持当前稳定状态并展示错误", "state_transition": "handling -> success|failed", "source_evidence": "evidence_bundle.contracts"})
    for module in confirmed_modules:
        if module != owner_file:
            sequence.append({"step": len(sequence) + 1, "from": owner_file, "to": module, "mode": "sync", "action": "更新直接参与需求的共享模块", "success": "共享模块完成状态或行为更新", "failure": "清理局部状态并保留可恢复路径", "state_transition": "component current -> component updated", "source_evidence": "evidence_bundle.anchors"})
    return {
        "applicable": applicable,
        "reason": "需求涉及接口/跨模块调用或已识别业务路由。" if applicable else "未识别到跨系统或接口调用影响。",
        "not_applicable_reason": "" if applicable else "本次只在已确认 owner 模块内处理本地行为，不新增第三方、跨仓、MQ、HTTP API 或回调交互。",
        "participants": participants if applicable else [],
        "sequence": sequence if applicable else [],
        "timeout_retry": "同步调用需确认超时、重试次数和用户可见错误；异步调用需确认补偿任务。",
        "idempotency": "写操作、多系统调用或重试路径必须绑定业务幂等键。",
        "consistency": "默认避免分布式事务；跨系统写入使用最终一致性、补偿或对账。",
        "mermaid_hint": "sequenceDiagram",
        "evidence_required": ["integration evidence", "timeout/retry evidence"] if applicable else [],
        "open_questions": ["确认真实上下游系统、调用方向和超时策略。"] if applicable else [],
    }


def mermaid_label(value: str) -> str:
    return value.replace('"', "'").replace("\n", " ").strip()


def render_process_flow_diagram(process_flow: list[dict[str, Any]]) -> str:
    if not process_flow:
        return ""
    flow = process_flow[0] if isinstance(process_flow[0], dict) else {}
    steps = [item for item in as_list(flow.get("steps")) if isinstance(item, dict)]
    if not steps:
        return ""
    lines = ["```mermaid", "flowchart TD"]
    for index, step in enumerate(steps, start=1):
        action = mermaid_label(str(step.get("action") or f"step {index}"))
        actor = mermaid_label(str(step.get("actor") or "actor"))
        node_id = f"S{index}"
        lines.append(f'    {node_id}["{index}. {actor}: {action}"]')
        if index > 1:
            lines.append(f"    S{index - 1} --> {node_id}")
    lines.append(f'    S{len(steps)} --> OK["Success: {mermaid_label(str(flow.get("success_end_state") or "acceptance complete"))}"]')
    for failure_index, failure_state in enumerate(as_list(flow.get("failure_end_states")), start=1):
        if failure_state:
            lines.append(f'    S{min(failure_index, len(steps))} -.-> F{failure_index}["Failure: {mermaid_label(str(failure_state))}"]')
    lines.append("```")
    return "\n".join(lines)


def render_system_sequence_diagram(system_sequence: dict[str, Any]) -> str:
    if not isinstance(system_sequence, dict) or system_sequence.get("applicable") is not True:
        return ""
    participants = [str(item) for item in as_list(system_sequence.get("participants")) if item]
    sequence = [item for item in as_list(system_sequence.get("sequence")) if isinstance(item, dict)]
    if not participants or not sequence:
        return ""
    lines = ["```mermaid", "sequenceDiagram", "    autonumber"]
    aliases = {participant: f"P{index}" for index, participant in enumerate(participants, start=1)}
    for participant, alias in aliases.items():
        lines.append(f"    participant {alias} as {mermaid_label(participant)}")
    for step in sequence:
        sender_name = str(step.get("from") or "UnknownFrom")
        receiver_name = str(step.get("to") or "UnknownTo")
        sender = aliases.get(sender_name, "PX")
        receiver = aliases.get(receiver_name, "PY")
        action = mermaid_label(str(step.get("action") or "action"))
        success = mermaid_label(str(step.get("success") or "success"))
        failure = mermaid_label(str(step.get("failure") or "failure"))
        lines.append(f"    {sender}->>{receiver}: {action}")
        lines.append(f"    Note over {receiver}: Success: {success}")
        lines.append(f"    Note over {receiver}: Failure: {failure}")
    lines.append("```")
    return "\n".join(lines)


def render_process_flow(spec: dict[str, Any], breakdown: list[dict[str, Any]], actors: list[str], summary: str) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    seen: set[str] = set()

    def append(actor: str, action: str, input_value: str, output: str, exception: str) -> None:
        clean = action.strip()
        if not clean or clean.lower() in seen:
            return
        seen.add(clean.lower())
        steps.append({"step": len(steps) + 1, "actor": actor, "action": clean, "input": input_value, "output": output, "exception": exception})

    for item in as_list(spec.get("business_flow")):
        if not isinstance(item, dict):
            continue
        structured = item.get("structured_step") if isinstance(item.get("structured_step"), dict) else {}
        append(
            str(item.get("actor") or structured.get("actor") or actors[0]),
            str(item.get("system_behavior") or (as_list(structured.get("system_actions")) or [""])[0]),
            str(item.get("trigger") or structured.get("entrypoint") or "business trigger"),
            str(item.get("expected_outcome") or structured.get("result") or "observable result"),
            "validation, permission, or dependency failure follows the documented exception path",
        )
        outcome = str(item.get("expected_outcome") or structured.get("result") or "").strip()
        behavior = str(item.get("system_behavior") or "").strip()
        if outcome and outcome != behavior:
            append("System", f"完成并验证结果：{outcome}", behavior or "business action", outcome, "result remains incomplete and the failure branch is recorded")
    if len(steps) == 1:
        first_acceptance = next((item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict) and item.get("criteria")), {})
        criterion = str(first_acceptance.get("criteria") or "").strip()
        if criterion:
            append("System", f"验证 {first_acceptance.get('id', 'acceptance')}：{criterion}", steps[0]["action"], criterion, "acceptance evidence remains incomplete")
    if not steps:
        for item in breakdown[:8]:
            append(actors[0], str(item.get("behavior_change") or item.get("summary") or summary), "user request/context", "observable business result", "existing validation or dependency failure")
    return [{
        "flow_name": summary,
        "actors": actors,
        "steps": steps,
        "success_end_state": "All mapped acceptance criteria pass.",
        "failure_end_states": ["Validation or permission failure", "Dependency unavailable", "Acceptance evidence missing"],
        "requirement_breakdown_ids": [str(item.get("id")) for item in breakdown if item.get("id")],
    }]


def render_mq_interactions(signals: dict[str, bool], owner_file: str, summary: str) -> list[dict[str, Any]]:
    applicable = bool(signals.get("mq"))
    if not applicable:
        return [{"applicable": False, "reason": "未识别到 MQ、事件、异步生产/消费信号。"}]
    return [{
        "applicable": True,
        "producer": owner_file,
        "consumer": "needs_confirmation",
        "topic_or_queue": "needs_confirmation",
        "tag_or_routing_key": "needs_confirmation",
        "trigger": f"业务动作完成后触发：{summary}",
        "payload_fields": ["business_id", "event_type", "occurred_at", "trace_id"],
        "idempotency_key": "business_id + event_type",
        "retry_policy": "明确最大重试次数、退避策略和可观测日志。",
        "dead_letter_or_compensation": "消费失败进入死信或补偿任务，需人工/自动重放策略。",
        "ordering": "如同一业务对象要求顺序消费，需说明分区键或串行化策略。",
        "compatibility": "新增字段保持向后兼容，已有消费者不能因未知字段失败。",
        "evidence_required": ["producer evidence", "consumer evidence", "retry/dead-letter evidence"],
        "open_questions": ["确认 topic/queue、消费者、消息体字段和失败补偿责任人。"],
    }]


def render_cache_strategy(signals: dict[str, bool], spec: dict[str, Any]) -> dict[str, Any]:
    blob = json_text(spec)
    strong_consistency = has_any_signal(blob, ["金额", "结算", "库存", "权限", "强一致", "支付", "amount", "settlement", "inventory", "permission", "strongly consistent", "strong consistency", "payment"])
    applicable = bool(signals.get("cache"))
    should_cache = applicable and not strong_consistency
    return {
        "applicable": applicable,
        "decision": "use_cache" if should_cache else "no_cache" if applicable else "not_applicable",
        "reason": (
            "存在高频读/统计/慢查询信号，且未识别强一致风险。"
            if should_cache else
            "涉及金额、结算、权限、库存或强一致判断，默认不加缓存，除非补充可靠失效和一致性方案。"
            if applicable else
            "未识别高频读、慢查询、统计、配置/字典类缓存需求。"
        ),
        "key_design": "needs_confirmation" if should_cache else "",
        "value_shape": "needs_confirmation" if should_cache else "",
        "ttl": "needs_confirmation" if should_cache else "",
        "invalidation": "write-through/delete-on-write/event invalidation must be defined" if should_cache else "",
        "consistency_risk": "缓存与源数据短暂不一致；强一致场景需禁用或只做只读辅助。" if applicable else "",
        "penetration_breakdown_avalanche": "空值缓存、互斥重建、TTL 抖动和限流。" if should_cache else "",
        "metrics": ["cache_hit_rate", "cache_rebuild_latency", "stale_read_count"] if should_cache else [],
        "evidence_required": ["cache hit/miss metrics", "stale-read validation"] if should_cache else [],
        "open_questions": ["确认 key、TTL、失效事件和一致性容忍度。"] if should_cache else [],
    }


def render_transaction_consistency(signals: dict[str, bool], summary: str) -> dict[str, Any]:
    applicable = bool(signals.get("consistency"))
    return {
        "applicable": applicable,
        "reason": "需求涉及写入、结算、金额、多表/多系统、重试或回滚。" if applicable else "未识别多表/多系统写入或强一致风险。",
        "not_applicable_reason": "" if applicable else "本次只调整前端交互和播放器生命周期，不新增数据写入、事务边界或跨系统一致性。",
        "boundary": "owner service/repository transaction boundary must be confirmed" if applicable else "",
        "local_transaction_boundary": "owner service/repository transaction boundary must be confirmed" if applicable else "",
        "distributed_transaction": "avoid by default; use eventual consistency with idempotency/compensation" if applicable else "",
        "idempotency": "business id + operation type + request id" if applicable else "",
        "compensation": "define retryable compensation job or manual repair path" if applicable else "",
        "reconciliation": "settlement/payment-like changes require reconciliation evidence" if applicable else "",
        "rollback": "code rollback plus data compatibility/compensation plan" if applicable else "",
        "evidence_required": ["idempotency test", "rollback/compensation evidence"] if applicable else [],
        "open_questions": ["确认本地事务边界、补偿责任和对账口径。"] if applicable else [],
    }


def render_observability_design(signals: dict[str, bool]) -> dict[str, Any]:
    return {
        "applicable": True,
        "reason": "所有实现需求都需要最小可观测性，跨系统/MQ/缓存场景需要专项指标。",
        "logs": ["business_id", "trace_id", "operation", "result", "failure_reason"],
        "metrics": ["request_count", "error_count", "latency_p95"],
        "traces": ["entrypoint", "downstream_call", "data_operation"],
        "alerts": ["error_rate_threshold", "latency_threshold"],
        "mq_metrics": ["lag", "dead_letter_count", "retry_count"] if signals.get("mq") else [],
        "cache_metrics": ["hit_rate", "rebuild_latency", "stale_read_count"] if signals.get("cache") else [],
        "evidence_required": ["log sample", "metric/alert evidence"],
    }


def render(spec: dict[str, Any], project_understanding: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = project_context(project_understanding or {})
    doc_id = str(spec.get("doc_id") or "")
    title = str(spec.get("title") or "")
    requirements = [item for item in as_list(spec.get("requirements")) if isinstance(item, dict)]
    acceptance = [item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]
    summary = str(spec.get("requirement_summary") or title)
    actors = [str(item) for item in as_list(spec.get("actors"))] or ["user"]
    req_id = str(requirements[0].get("id") if requirements else "REQ-1")
    ac_id = str(acceptance[0].get("id") if acceptance else "AC-1")
    breakdown = requirement_breakdown(spec)
    owner_module = ctx["modules"][0] if ctx["modules"] else "target module to be confirmed"
    read_first = ctx["entrypoints"] + ctx["files"][:5]
    fallback_owner = next((item for item in read_first if item.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs", ".vue"))), owner_module)
    owner_file, entrypoint_confidence = select_owner_file(summary, breakdown, ctx, fallback_owner)
    ranked_paths = [str(item.get("path")) for item in as_list(entrypoint_confidence.get("ranked_candidates")) if isinstance(item, dict) and item.get("path")]
    read_first = [owner_file, *ranked_paths, *[item for item in read_first if item == owner_file or not is_generic_entrypoint(item)]]
    read_first = list(dict.fromkeys(item for item in read_first if item))
    route_subject = " ".join([summary, " ".join(str(item.get("summary") or "") for item in breakdown)])
    business_routes = sorted(
        [item for item in ctx["routes"] if is_business_route(item) and route_relevance_score(item, route_subject) > 0],
        key=lambda item: route_relevance_score(item, route_subject),
        reverse=True,
    )
    location_evidence = ctx.get("source_location_evidence") if isinstance(ctx.get("source_location_evidence"), dict) else {}
    confirmed_contracts = [str(item) for item in as_list(location_evidence.get("confirmed_contracts") or location_evidence.get("contracts")) if item]
    explicit_contracts = explicit_contract_refs_from_spec(spec)
    route_refs = confirmed_contracts or explicit_contracts or [route_ref(item) for item in business_routes[:5]]
    config_refs = [str(item.get("path")) for item in ctx["config_items"][:5]]
    test_evidence = [f"{cmd} evidence" for cmd in ctx["test_hints"][:3]] or ["test evidence"]
    applicability = {str(item.get("area")): str(item.get("status")) for item in as_list(spec.get("impact_applicability")) if isinstance(item, dict)}
    impact_areas = {area for area, status in applicability.items() if status == "required"} if applicability else {str(item.get("area")) for item in as_list(spec.get("impact_surface")) if isinstance(item, dict)}
    expert_readiness_gaps = [item for item in as_list(spec.get("expert_readiness_gaps")) if isinstance(item, dict)]
    requirements_understanding = spec.get("requirements_understanding") if isinstance(spec.get("requirements_understanding"), dict) else {}
    design_allowed = bool(spec.get("design_allowed", requirements_understanding.get("design_allowed", True)))
    implementation_allowed = bool(spec.get("implementation_allowed", requirements_understanding.get("implementation_allowed", design_allowed)))
    ambiguities = [item for item in as_list(spec.get("ambiguities")) if isinstance(item, dict)]
    understanding_blockers = [item for item in as_list(requirements_understanding.get("blockers")) if isinstance(item, dict)]
    location_evidence = ctx.get("source_location_evidence") if isinstance(ctx.get("source_location_evidence"), dict) else {}
    if location_evidence and location_evidence.get("decision") != "pass":
        understanding_blockers.extend(
            item for item in as_list(location_evidence.get("blockers")) if isinstance(item, dict)
        )
        design_allowed = False
        implementation_allowed = False
    requirements_understanding_gate = {
        "decision": "block" if location_evidence and location_evidence.get("decision") != "pass" else requirements_understanding.get("decision") or ("pass" if design_allowed else "needs_clarification"),
        "design_allowed": design_allowed,
        "implementation_allowed": implementation_allowed and design_allowed,
        "understanding_confidence": spec.get("understanding_confidence") or requirements_understanding.get("confidence") or ("high" if design_allowed else "low"),
        "business_intent": spec.get("business_intent") or requirements_understanding.get("business_intent") or "",
        "business_flow": spec.get("business_flow") or requirements_understanding.get("business_flow") or [],
        "business_flow_model": spec.get("business_flow_model") or requirements_understanding.get("business_flow_model") or {},
        "business_closure_model": spec.get("business_closure_model") or requirements_understanding.get("business_closure_model") or {},
        "entrypoints": spec.get("entrypoints") or requirements_understanding.get("entrypoints") or [],
        "current_business_state": spec.get("current_business_state") or requirements_understanding.get("current_business_state") or {},
        "current_state_evidence": spec.get("current_state_evidence") or requirements_understanding.get("current_state_evidence") or [],
        "evidence_match_table": spec.get("evidence_match_table") or requirements_understanding.get("evidence_match_table") or [],
        "state_machine": spec.get("state_machine") or requirements_understanding.get("state_machine") or {},
        "business_goal_quality": spec.get("business_goal_quality") or requirements_understanding.get("business_goal_quality") or {},
        "repo_impact_map": spec.get("repo_impact_map") or requirements_understanding.get("repo_impact_map") or {},
        "dependency_chain": spec.get("dependency_chain") or requirements_understanding.get("dependency_chain") or {},
        "runtime_dependency_graph": spec.get("runtime_dependency_graph") or requirements_understanding.get("runtime_dependency_graph") or {},
        "trigger_conditions": spec.get("trigger_conditions") or requirements_understanding.get("trigger_conditions") or [],
        "preconditions": spec.get("preconditions") or requirements_understanding.get("preconditions") or [],
        "postconditions": spec.get("postconditions") or requirements_understanding.get("postconditions") or [],
        "blockers": understanding_blockers,
        "ambiguities": ambiguities,
        "required_action": "resolve requirement clarification questions before technical design can be treated as implementation-ready" if not design_allowed else "none",
    }
    if not design_allowed:
        decision_confidence = "low"
    elif expert_readiness_gaps or spec.get("open_questions"):
        decision_confidence = "medium"
    else:
        decision_confidence = "high"
    problem = build_problem_analysis(spec, ctx, summary, breakdown, owner_file, read_first, route_refs, entrypoint_confidence)
    technical_options, comparison_matrix, score_summary, selected_solution = build_technical_options(spec, summary, owner_file, breakdown, route_refs, test_evidence, problem)
    signals = impact_signals(spec, breakdown, route_refs)
    data_model_design = render_data_model_design(signals, spec, breakdown, owner_file)
    process_flow = render_process_flow(spec, breakdown, actors, summary)
    system_interaction_sequence = render_system_interaction_sequence(signals, route_refs, owner_file, summary, [str(item) for item in as_list(entrypoint_confidence.get("confirmed_anchors"))])
    module_decomposition = [{
        "module": owner_file,
        "responsibility": str(item.get("summary") or summary),
        "input": "request data",
        "output": "updated behavior",
        "dependencies": route_refs + config_refs or ["none confirmed"],
        "cohesion_reason": f"Keep requirement behavior in {ctx['project']} owner file/module.",
        "coupling_control": "Use existing contracts and avoid duplicating upstream business rules.",
        "requirement_breakdown_id": item.get("id"),
        "entrypoint_confidence": entrypoint_confidence.get("level"),
    } for item in breakdown]
    for path in as_list(entrypoint_confidence.get("confirmed_anchors")):
        if path and path != owner_file:
            module_decomposition.append({
                "module": str(path),
                "responsibility": f"Support {summary} through the directly confirmed source call chain.",
                "input": f"state or call from {owner_file}",
                "output": "updated behavior",
                "dependencies": [owner_file],
                "cohesion_reason": "The source-location evidence confirms this module participates directly in the requirement flow.",
                "coupling_control": "Keep the existing boundary and contract between confirmed modules.",
                "requirement_breakdown_id": breakdown[0].get("id") if breakdown else "BRK-1",
                "entrypoint_confidence": entrypoint_confidence.get("level"),
            })
    source_literals = extract_source_literals(spec)
    known_literals = {str(item.get("literal")) for item in source_literals if isinstance(item, dict)}
    for contract in confirmed_contracts:
        if contract not in known_literals:
            source_literals.append({"literal": contract, "source": "source_location_evidence.confirmed_contracts", "required_binding": True})
    constraint_model = generic_constraint_model(spec)
    return {
        "schema": "codex-technical-design-v1",
        "decision": "pass" if design_allowed else "block",
        "blockers": understanding_blockers,
        "doc_id": doc_id,
        "title": title,
        "project_context": {
            "project": ctx["project"],
            "repo_root": ctx["repo_root"],
            "local_project_binding": ctx["local_project_binding"],
            "framework_hints": ctx["framework_hints"],
            "read_first": read_first,
            "test_command_hints": ctx["test_hints"],
            "test_file_hints": ctx["test_file_hints"],
        },
        "source_location_evidence": location_evidence,
        "local_project_binding": ctx["local_project_binding"],
        "source_literals": source_literals,
        "constraint_model": constraint_model,
        "forbidden_reuse_paths": constraint_model["forbidden_reuse_paths"],
        "forbidden_modules": constraint_model["forbidden_modules"],
        "forbidden_contracts": constraint_model["forbidden_contracts"],
        "forbidden_behaviors": constraint_model["forbidden_behaviors"],
        "out_of_scope_patterns": constraint_model["out_of_scope_patterns"],
        "design_scope": spec.get("scope") or {"in_scope": [summary], "out_of_scope": [], "assumptions": [], "non_goals": []},
        "impact_applicability": as_list(spec.get("impact_applicability")),
        "scope_model": spec.get("scope_model") or {},
        "requirements_understanding": requirements_understanding,
        "requirements_understanding_gate": requirements_understanding_gate,
        "business_intent": requirements_understanding_gate["business_intent"],
        "business_flow": requirements_understanding_gate["business_flow"],
        "business_closure_model": requirements_understanding_gate["business_closure_model"],
        "entrypoints": requirements_understanding_gate["entrypoints"],
        "state_machine": requirements_understanding_gate["state_machine"],
        "business_goal_quality": requirements_understanding_gate["business_goal_quality"],
        "repo_impact_map": requirements_understanding_gate["repo_impact_map"],
        "dependency_chain": requirements_understanding_gate["dependency_chain"],
        "runtime_dependency_graph": requirements_understanding_gate["runtime_dependency_graph"],
        "problem_analysis": problem,
        "current_state_analysis": build_current_state_analysis(problem, owner_module, route_refs),
        "requirement_breakdown": breakdown,
        "code_entrypoint_confidence": entrypoint_confidence,
        "requirement_trace": [{"requirement_id": str(item.get("id")), "summary": str(item.get("summary"))} for item in requirements],
        "business_rule_mapping": [
            {"requirement_id": req_id, "technical_enforcement": str(rule.get("rule")), "source_of_truth": "spec.business_rules"}
            for rule in as_list(spec.get("business_rules")) if isinstance(rule, dict)
        ] or [{"requirement_id": req_id, "technical_enforcement": "Implement behavior described by normalized spec.", "source_of_truth": "spec.requirements"}],
        "process_flow": process_flow,
        "process_flow_diagram": render_process_flow_diagram(process_flow),
        "module_decomposition": module_decomposition,
        "logical_data_flow": [{"source": route_refs[0] if route_refs else "existing source", "transform": str(item.get("summary") or summary), "destination": owner_file, "owner": ctx["project"], "data_security": "classify during security review", "requirement_breakdown_id": item.get("id")} for item in breakdown],
        "target_behavior": [{"requirement_id": str(item.get("id") or req_id), "behavior": str(item.get("summary") or summary)} for item in requirements] or [{"requirement_id": req_id, "behavior": summary}],
        "api_contracts": [api_contract_for_breakdown(route_refs, item) for item in breakdown],
        "interface_examples": [] if applicability.get("api") in {"excluded", "not_applicable"} else [{"name": route_refs[0] if route_refs else "no API request expected", "request": route_refs[0] if route_refs else "no API request expected", "response": f"response contract for {route_refs[0]}" if route_refs else "no API response change expected", "error_response": f"error contract for {route_refs[0]}" if route_refs else "no API error contract change expected"}],
        "compatibility_strategy": [{"old_consumer": "existing consumers", "old_data": "existing data", "rollback": "revert changed behavior", "behavior": "preserve backward compatibility"}],
        "compatibility_matrix": [{"consumer": "existing consumers", "old_behavior": "current behavior before this requirement", "new_behavior": summary, "compatibility": "backward compatible by default", "rollback_behavior": "revert changed behavior"}],
        "data_design": [] if applicability.get("data") in {"excluded", "not_applicable"} else [{"read_rule": f"{item.get('id')}: read through {owner_file}", "write_rule": f"{item.get('id')}: write through {owner_file} only if this slice changes state", "migration": "none unless this slice changes schema/data backfill", "field_impact": item.get("field_impact"), "requirement_breakdown_id": item.get("id")} for item in breakdown],
        "data_model_design": data_model_design,
        "table_schema_changes": render_table_schema_changes(data_model_design),
        "system_interaction_sequence": system_interaction_sequence,
        "system_sequence_diagram": render_system_sequence_diagram(system_interaction_sequence),
        "mq_interactions": render_mq_interactions(signals, owner_file, summary),
        "cache_strategy": render_cache_strategy(signals, spec),
        "transaction_consistency": render_transaction_consistency(signals, summary),
        "observability_design": render_observability_design(signals),
        "permission_model": [{"role": actor, "rule": "preserve existing permission boundary", "negative_case": "unauthorized user cannot access changed behavior"} for actor in actors],
        "field_api_permission_impact": [
            {
                "requirement_breakdown_id": item.get("id"),
                "summary": item.get("summary"),
                "field_impact": item.get("field_impact"),
                "api_impact": item.get("api_impact"),
                "permission_impact": item.get("permission_impact"),
                "impact_areas": item.get("impact_areas"),
                "owner_entrypoint": owner_file,
                "entrypoint_confidence": entrypoint_confidence.get("level"),
            }
            for item in breakdown
        ],
        "low_confidence_items": [
            {
                "item": "primary_code_entrypoint",
                "level": entrypoint_confidence.get("level"),
                "selected_entrypoint": owner_file,
                "reason": entrypoint_confidence.get("blocker") or "entrypoint confidence is not high",
                "required_action": "inspect matched feature modules and update design before implementation",
            }
        ] if entrypoint_confidence.get("level") != "high" else [],
        "exception_and_edge_cases": [{"case": "missing/invalid input", "handling": "return validation error or preserve existing fallback"}],
        "non_functional_requirements": [{"type": "performance", "impact": "no extra heavy IO unless selected option requires it"}, {"type": "security", "impact": "no sensitive data exposure"}],
        "solution_options": technical_options,
        "option_comparison_matrix": comparison_matrix,
        "option_score_summary": score_summary,
        "selected_solution": selected_solution,
        "decision_confidence": {
            "level": decision_confidence,
            "reason": "Requirement understanding is not sufficient for design." if not design_allowed else "Open questions or expert readiness gaps lower confidence." if decision_confidence != "high" else "Spec has no open questions and no expert readiness gaps.",
            "confidence_reducers": expert_readiness_gaps + understanding_blockers + ambiguities,
        },
        "implementation_invariants": [
            {"invariant": "Preserve existing permission and validation behavior unless explicitly changed.", "evidence": "negative permission and regression tests"},
            {"invariant": "Keep edits inside delivery_plan.allowed_files unless design is revised.", "evidence": "edit permit and write guard audit"},
            {"invariant": "Do not change API/data contracts without compatibility evidence.", "evidence": "contract or migration test evidence"},
        ],
        "expert_review_checklist": [
            {"item": "All high-risk impacts have explicit evidence paths.", "status": "ready" if impact_areas else "review"},
            {"item": "Selected option explains rejected alternatives.", "status": "ready"},
            {"item": "Rollback and compatibility are testable.", "status": "ready"},
            {"item": "Derived spec gaps are resolved or accepted before implementation.", "status": "review" if expert_readiness_gaps else "ready"},
            {"item": "Requirement understanding allows design and implementation planning.", "status": "ready" if design_allowed else "blocked"},
        ],
        "design_traceability_matrix": [
            {
                "requirement_id": str(item.get("id") or req_id),
                "requirement_breakdown_refs": [row.get("id") for row in breakdown],
                "process_flow_refs": [title or summary],
                "module_refs": list(dict.fromkeys(str(mod.get("module")) for mod in as_list([{"module": owner_file}]) if mod.get("module"))),
                "data_flow_refs": [f"{route_refs[0] if route_refs else 'existing source'}->{owner_file}"],
                "api_contract_refs": route_refs or ["No external API contract change; implementation stays inside confirmed owner/module boundary"],
                "ui_ue_refs": ["affected UI if any"],
                "test_refs": [f"TEST-{item.get('id') or req_id}"],
                "acceptance_refs": [str(ac.get("id") or ac_id) for ac in acceptance] or [ac_id],
                "selected_option_id": selected_solution.get("selected_option_id"),
                "decision_reason": selected_solution.get("selection_reason"),
            }
            for item in requirements
        ] or [{"requirement_id": req_id, "requirement_breakdown_refs": [row.get("id") for row in breakdown], "process_flow_refs": [title or summary], "module_refs": [owner_file], "data_flow_refs": [f"{route_refs[0] if route_refs else 'existing source'}->{owner_file}"], "api_contract_refs": route_refs or ["No external API contract change; implementation stays inside confirmed owner/module boundary"], "ui_ue_refs": ["affected UI if any"], "test_refs": [f"TEST-{req_id}"], "acceptance_refs": [ac_id], "selected_option_id": selected_solution.get("selected_option_id"), "decision_reason": selected_solution.get("selection_reason")}],
        "acceptance_mapping": [{"acceptance_id": str(item.get("id") or ac_id), "design_refs": [summary], "evidence_required": as_list(item.get("evidence_required")) or test_evidence} for item in acceptance] or [{"acceptance_id": ac_id, "design_refs": [summary], "evidence_required": test_evidence}],
        "ui_ue_design": [{"page_or_route": route_refs[0] if route_refs else "confirm if UI is affected", "user_goal": summary, "entry_point": "existing entry", "layout": "preserve existing layout unless requirement changes it", "interaction_flow": ["open affected behavior", "perform action", "verify result"], "states": ["loading", "success", "error"], "field_rules": ["preserve existing field validation and visibility"], "permission_visibility": "preserve role visibility", "acceptance_evidence": "browser evidence if UI changed"}],
        "test_strategy": [{"summary": f"Validate acceptance criteria for {summary}; detailed cases belong in test_design.json.", "evidence": test_evidence, "type": "strategy_summary", "test_design_ref": "test_design.json"}],
        "test_design_ref": "test_design.json",
        "open_questions": spec.get("open_questions", []),
    }


def merge_specialized_artifacts(result: dict[str, Any], artifact_paths: dict[str, Path | None]) -> dict[str, Any]:
    architecture_framing = load_json(artifact_paths.get("architecture_framing")) if artifact_paths.get("architecture_framing") else {}
    ui_design = load_json(artifact_paths.get("ui_ue_design")) if artifact_paths.get("ui_ue_design") else {}
    api_contract = load_json(artifact_paths.get("api_contract_design")) if artifact_paths.get("api_contract_design") else {}
    data_model = load_json(artifact_paths.get("data_model_design")) if artifact_paths.get("data_model_design") else {}
    domain_model = load_json(artifact_paths.get("domain_model_design")) if artifact_paths.get("domain_model_design") else {}
    observability = load_json(artifact_paths.get("observability_design")) if artifact_paths.get("observability_design") else {}

    result["specialized_design_artifacts"] = {
        name: str(path)
        for name, path in artifact_paths.items()
        if path and path.exists()
    }
    if architecture_framing and architecture_framing.get("decision") in {"pass", "block"}:
        result["architecture_framing_ref"] = "architecture_framing.json"
        result["architecture_framing"] = architecture_framing
        boundary = architecture_framing.get("system_boundary") if isinstance(architecture_framing.get("system_boundary"), dict) else {}
        if boundary.get("owner_repo"):
            result["project_context"]["architecture_owner_repo"] = boundary.get("owner_repo")
        if architecture_framing.get("runtime_entrypoints"):
            result["entrypoints"] = architecture_framing.get("runtime_entrypoints")
        if architecture_framing.get("dependency_graph"):
            result["runtime_dependency_graph"] = architecture_framing.get("dependency_graph")
        result["expert_review_checklist"].append({
            "item": "Architecture framing is consumed before detailed technical design.",
            "status": "ready" if architecture_framing.get("decision") == "pass" else "blocked",
        })
    if ui_design and ui_design.get("decision") not in {"not_applicable", "block"}:
        screens = [item for item in as_list(ui_design.get("screens")) if isinstance(item, dict)]
        summary = ui_design.get("experience_summary") if isinstance(ui_design.get("experience_summary"), dict) else {}
        result["ui_ue_design"] = [{
            "page_or_route": str(screen.get("page_or_route") or summary.get("entry_surface") or ""),
            "user_goal": str(summary.get("user_goal") or ""),
            "entry_point": str(summary.get("trigger_action") or ""),
            "layout": screen.get("layout_zones") or screen.get("layout") or [],
            "interaction_flow": as_list((ui_design.get("interaction_flows") or [{}])[0].get("steps")) if as_list(ui_design.get("interaction_flows")) and isinstance(as_list(ui_design.get("interaction_flows"))[0], dict) else [],
            "states": [str(item.get("state")) for item in as_list(ui_design.get("state_matrix")) if isinstance(item, dict)],
            "field_rules": as_list(ui_design.get("content_i18n")),
            "permission_visibility": "frontend visibility follows UI/UE permission state; backend authorization remains authoritative",
            "acceptance_evidence": ", ".join(str(item) for item in as_list(ui_design.get("acceptance_evidence"))),
            "source_artifact": "ui_ue_design.json",
        } for screen in (screens or [{}])]
    if api_contract and api_contract.get("decision") not in {"not_applicable", "block"}:
        result["api_contracts"] = as_list(api_contract.get("contracts")) or result.get("api_contracts", [])
        result["api_contract_design_ref"] = "api_contract_design.json"
    if data_model and data_model.get("decision") not in {"not_applicable", "block"}:
        result["data_model_design"] = data_model
        result["table_schema_changes"] = as_list(data_model.get("tables")) or result.get("table_schema_changes", [])
        result["data_model_design_ref"] = "data_model_design.json"
    if domain_model and domain_model.get("decision") == "pass":
        result["domain_model_design_ref"] = "domain_model_design.json"
        result["business_intent"] = domain_model.get("business_intent") or result.get("business_intent")
        result["business_flow"] = domain_model.get("business_flow") or result.get("business_flow")
        result["state_machine"] = domain_model.get("state_machine") or result.get("state_machine")
    if observability and observability.get("decision") == "pass":
        result["observability_design"] = observability
        result["observability_design_ref"] = "observability_design.json"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Render technical design from normalized spec")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--project-understanding")
    parser.add_argument("--architecture-framing")
    parser.add_argument("--ui-ue-design")
    parser.add_argument("--api-contract-design")
    parser.add_argument("--data-model-design")
    parser.add_argument("--domain-model-design")
    parser.add_argument("--observability-design")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = render(load_json(Path(args.spec)), load_project_understanding(Path(args.project_understanding)) if args.project_understanding else None)
    result = merge_specialized_artifacts(result, {
        "architecture_framing": Path(args.architecture_framing) if args.architecture_framing else None,
        "ui_ue_design": Path(args.ui_ue_design) if args.ui_ue_design else None,
        "api_contract_design": Path(args.api_contract_design) if args.api_contract_design else None,
        "data_model_design": Path(args.data_model_design) if args.data_model_design else None,
        "domain_model_design": Path(args.domain_model_design) if args.domain_model_design else None,
        "observability_design": Path(args.observability_design) if args.observability_design else None,
    })
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
