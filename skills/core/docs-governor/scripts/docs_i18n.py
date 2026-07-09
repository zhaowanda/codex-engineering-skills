#!/usr/bin/env python3
from __future__ import annotations

import json
from typing import Any


LANG_ZH = "zh"
LANG_EN = "en"


def normalize_language(language: str = LANG_EN) -> str:
    return LANG_ZH if str(language).lower() in {"zh", "cn", "chinese", "中文"} else LANG_EN


SECTION_TITLES = {
    "data_model_schema": {LANG_ZH: "数据模型与表结构", LANG_EN: "Data Model And Table Schema"},
    "system_sequence": {LANG_ZH: "多系统交互时序", LANG_EN: "Multi-System Interaction Sequence"},
    "mq_interactions": {LANG_ZH: "MQ 上下游与触发机制", LANG_EN: "MQ Upstream, Downstream, And Trigger"},
    "cache_strategy": {LANG_ZH: "缓存策略评估", LANG_EN: "Cache Strategy Assessment"},
    "transaction_consistency": {LANG_ZH: "事务与一致性", LANG_EN: "Transaction And Consistency"},
    "observability_design": {LANG_ZH: "可观测性设计", LANG_EN: "Observability Design"},
}


FIELD_LABELS = {
    LANG_ZH: {
        "existing_behavior": "现有行为",
        "code_entrypoints": "代码入口",
        "known_constraints": "已知约束",
        "reuse_points": "可复用点",
        "system_context": "系统上下文",
        "repo_entrypoints": "仓库入口",
        "upstream_downstream": "上下游",
        "constraints": "约束",
        "module": "模块",
        "responsibility": "职责",
        "input": "输入",
        "output": "输出",
        "coupling_control": "耦合控制",
        "contract": "契约",
        "compatibility": "兼容性",
        "old_consumer_impact": "存量消费方影响",
        "name": "名称",
        "request": "请求",
        "response": "响应",
        "error_response": "错误响应",
        "read_rule": "读取规则",
        "write_rule": "写入规则",
        "migration": "迁移",
        "rollback": "回滚",
        "role": "角色",
        "rule": "规则",
        "negative_case": "反向用例",
        "case": "场景",
        "summary": "摘要",
        "handling": "处理方式",
        "page_or_route": "页面/路由",
        "user_goal": "用户目标",
        "entry_point": "入口",
        "permission_visibility": "权限可见性",
        "acceptance_evidence": "验收证据",
        "from": "来源",
        "to": "目标",
        "change": "变更",
        "step": "步骤",
        "actor": "参与方",
        "action": "动作",
        "failure_handling": "失败处理",
        "repo": "仓库",
        "artifact": "制品",
        "order": "顺序",
        "config_change": "配置变更",
        "restart_required": "是否重启",
        "steps": "步骤",
        "data_risk": "数据风险",
        "acceptance_id": "验收项",
        "design_refs": "设计引用",
        "evidence_required": "所需证据",
        "type": "类型",
        "evidence": "证据",
        "signal": "信号",
        "owner": "负责人",
        "trigger": "触发条件",
        "applicable": "是否适用",
        "entities": "实体/表候选",
        "field_rules": "字段规则",
        "ownership": "数据归属",
        "read_write_rules": "读写规则",
        "migration_strategy": "迁移策略",
        "rollback_strategy": "回滚策略",
        "table": "表",
        "field": "字段",
        "nullable": "是否可空",
        "default": "默认值",
        "participants": "参与方",
        "sequence": "时序步骤",
        "timeout_retry": "超时与重试",
        "idempotency": "幂等",
        "consistency": "一致性",
        "producer": "生产方",
        "consumer": "消费方",
        "topic_or_queue": "Topic/队列",
        "payload_fields": "消息字段",
        "idempotency_key": "幂等键",
        "retry_policy": "重试策略",
        "dead_letter_or_compensation": "死信/补偿",
        "not_applicable_reason": "不适用原因",
        "decision": "决策",
        "key_design": "Key 设计",
        "value_shape": "Value 结构",
        "ttl": "TTL",
        "invalidation": "失效机制",
        "consistency_risk": "一致性风险",
        "reason": "原因",
        "boundary": "事务边界",
        "compensation": "补偿",
        "logs": "日志",
        "metrics": "指标",
        "traces": "链路",
        "alerts": "告警",
    },
    LANG_EN: {
        "page_or_route": "page/route",
        "user_goal": "user goal",
        "entry_point": "entry point",
        "permission_visibility": "permission visibility",
        "acceptance_evidence": "acceptance evidence",
        "old_consumer_impact": "consumer impact",
        "failure_handling": "failure handling",
        "data_risk": "data risk",
    },
}


STATUS_TEXT = {
    LANG_ZH: {
        "needs_confirmation": "需结合代码和数据库核对",
        "needs_code_confirmation": "需结合代码核对",
        "not_applicable": "不适用",
        "use_cache": "使用缓存",
        "no_cache": "不使用缓存",
        "unknown": "未知",
        "draft": "草稿",
        "ready": "就绪",
        "ready_for_design": "可进入设计",
        "needs_completion": "需要补齐",
        "needs_revision": "需要修订",
        "pass": "通过",
        "block": "阻塞",
        "low": "低",
        "medium": "中",
        "high": "高",
    },
    LANG_EN: {},
}


PHRASE_REPLACEMENTS_ZH = {
    "target module to be confirmed": "需结合代码核对的责任模块",
    "existing entrypoint to be confirmed": "需结合代码核对的现有入口",
    "待确认目标模块": "需结合代码核对的责任模块",
    "existing contract": "现有契约",
    "existing producer": "现有生产方",
    "User/Client": "用户或客户端",
    "owner_module": "责任模块",
    "owns code changes": "负责代码变更",
    "no-migration evidence": "无迁移证据",
    "code rollback plus data compatibility/compensation plan": "代码回滚，并配套数据兼容或补偿方案",
    "code rollback plus data 兼容性/compensation plan": "代码回滚，并配套数据兼容或补偿方案",
    "code rollback plus schema/data rollback plan if migration is applied": "如执行迁移，需配套代码回滚和结构/数据回滚方案",
    "owner service/repository transaction boundary must be confirmed": "需确认责任服务或仓库的事务边界",
    "business id + operation type + request id": "业务 ID + 操作类型 + 请求 ID",
    "define retryable compensation job or manual repair path": "定义可重试补偿任务或人工修复路径",
    "write through": "通过",
    "only if this slice changes state": "仅在该子需求改变状态时写入",
    "unless this slice changes schema/data backfill": "除非该子需求改变表结构或数据回填",
    "primary code entrypoint is generic or weakly matched; inspect project manually before implementation": "主代码入口匹配较弱，实施前需人工核对项目代码",
    "inspect matched feature modules and update design before implementation": "实施前核对匹配到的功能模块并更新设计",
    "before implementation": "实施前",
}


FALLBACKS = {
    "data_model_missing": {LANG_ZH: "未同步到数据模型设计。", LANG_EN: "No data model design was synced."},
    "table_schema_missing": {
        LANG_ZH: "未同步到表结构变更；如果无表结构影响，应在数据模型中说明。",
        LANG_EN: "No table schema changes were synced; no-impact cases should be explained in the data model.",
    },
    "system_sequence_missing": {LANG_ZH: "未同步到多系统交互时序。", LANG_EN: "No system interaction sequence was synced."},
    "mq_missing": {
        LANG_ZH: "未同步到 MQ 上下游设计；涉及异步消息时必须补齐。",
        LANG_EN: "No MQ interaction design was synced; asynchronous changes must define this.",
    },
    "cache_missing": {LANG_ZH: "未同步到缓存策略。", LANG_EN: "No cache strategy was synced."},
    "transaction_missing": {LANG_ZH: "未同步到事务与一致性设计。", LANG_EN: "No transaction consistency design was synced."},
    "observability_missing": {LANG_ZH: "未同步到可观测性设计。", LANG_EN: "No observability design was synced."},
}


def section_title(key: str, language: str = LANG_EN) -> str:
    lang = normalize_language(language)
    return SECTION_TITLES.get(key, {}).get(lang, key)


def fallback(key: str, language: str = LANG_EN) -> str:
    lang = normalize_language(language)
    return FALLBACKS.get(key, {}).get(lang, "TBD" if lang == LANG_EN else "待补充")


def label(field: str, language: str = LANG_EN) -> str:
    lang = normalize_language(language)
    return FIELD_LABELS.get(lang, {}).get(field, field)


def translate_text(value: str, language: str = LANG_EN) -> str:
    lang = normalize_language(language)
    if lang == LANG_EN:
        return value
    rendered = STATUS_TEXT[LANG_ZH].get(value, value)
    for source, target in sorted(PHRASE_REPLACEMENTS_ZH.items(), key=lambda item: len(item[0]), reverse=True):
        rendered = rendered.replace(source, target)
    return rendered


def render_value(value: Any, language: str = LANG_EN, default: str | None = None) -> str:
    lang = normalize_language(language)
    fallback_text = default if default is not None else ("待补充" if lang == LANG_ZH else "TBD")
    if value in (None, "", [], {}):
        return fallback_text
    if isinstance(value, bool):
        return ("是" if value else "否") if lang == LANG_ZH else ("yes" if value else "no")
    if isinstance(value, list):
        rendered = [render_value(item, lang, fallback_text) for item in value if item not in (None, "", [], {})]
        return ("；" if lang == LANG_ZH else "; ").join(rendered) if rendered else fallback_text
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            if item in (None, "", [], {}):
                continue
            parts.append(f"{label(str(key), lang)}={render_value(item, lang, fallback_text)}")
        return ("，" if lang == LANG_ZH else ", ").join(parts) if parts else fallback_text
    if isinstance(value, (int, float)):
        return str(value)
    raw = str(value)
    if lang == LANG_ZH:
        return translate_text(raw, lang)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return raw
