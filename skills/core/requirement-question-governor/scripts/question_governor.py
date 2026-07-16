#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

SCHEMA = "codex-open-questions-v1"
PLACEHOLDER_QUESTIONS = {
    "待确认问题",
    "确认问题",
    "clarification question",
    "question",
    "tbd",
    "to be confirmed",
}
ENGLISH_TEMPLATE_PREFIXES = (
    "what is ",
    "what are ",
    "which ",
    "confirm ",
    "clarify ",
    "resolve ",
)


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def question_key(question: dict[str, Any]) -> str:
    return str(question.get("question") or "").strip().lower()


def has_cjk(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def spec_prefers_zh(spec: dict[str, Any]) -> bool:
    payload = json.dumps(spec, ensure_ascii=False)
    return has_cjk(payload)


def is_placeholder_question(value: str) -> bool:
    normalized = value.strip().lower()
    return not normalized or normalized in PLACEHOLDER_QUESTIONS or normalized.rstrip("？?") in PLACEHOLDER_QUESTIONS


def localize_question(question: str, category: str, spec: dict[str, Any]) -> str:
    if not spec_prefers_zh(spec) or has_cjk(question):
        return question
    translations = {
        "business_goal": "这个需求的真实业务目标、当前痛点、受影响用户和可观察成功信号分别是什么？",
        "business_flow": "完整业务流程是什么，包括参与者、前置条件、入口、触发方式、系统行为、成功结果和失败处理？",
        "actor_entrypoint": entrypoint_question(spec),
        "acceptance": "哪些可执行的正向和反向验收用例能够证明每个业务分支都满足？",
        "state_transition": "准确的状态流转、触发时机、非法流转和下游影响是什么？",
        "ambiguous_action": "本次到底需要改变什么具体行为，哪些既有行为必须保持不变？",
        "ambiguous_flow": "这条流程的来源、目标、触发时机、重试、幂等和完成条件分别是什么？",
        "ambiguous_defect": "实际观察到的问题、期望行为、影响数据/用户、复现或检测条件分别是什么？",
        "ambiguous_scope": "哪些对象、用户、系统和场景在本次范围内，哪些明确不在范围内？",
        "ambiguous_rule": "具体规则、默认值、优先级、例外情况和回滚行为是什么？",
        "ambiguous_exception": "哪些异常场景需要处理、忽略、重试，或者暴露给用户/运营？",
        "ambiguous_state": "哪个状态由谁在什么时机更新，会产生哪些下游影响？",
        "business_closure": business_closure_question(spec),
        "state_machine": "本需求涉及的状态机、重试策略、幂等键、超时规则、补偿规则和非法流转是什么？",
        "dependency_chain": "按顺序排列的上下游系统、消息 topic、API 契约、消费者和联调证据是什么？",
        "repo_impact": "哪些仓库/服务分别负责本需求的各部分，哪些是一度或多度依赖？",
        "understanding_score": "当前理解薄弱点需要补齐哪些业务目标、流程、入口、证据或状态规则？",
        "success_metric": "这个需求需要观察什么量化成功阈值？",
        "scope_boundary": "本次变更明确不包含哪些范围？",
        "current_business_state": current_state_evidence_question(spec),
        "api_contract": "本次涉及哪些端点、请求/响应字段、错误码、兼容规则和既有消费者？",
        "data_rule": "涉及哪些数据字段、定义、筛选、空值/默认值和排序规则？",
        "configuration": "配置默认值、环境覆盖、灰度范围和回滚行为是什么？",
        "permission": "哪些未授权角色、租户/数据范围和反向权限用例必须失败？",
    }
    return translations.get(category, f"请澄清需求歧义：{question}")


def semantic_question_key(question: dict[str, Any]) -> str:
    category = str(question.get("category") or "general")
    aliases = {
        "understanding_score": str(question.get("source") or "").rsplit(".", 1)[-1].replace("_score", ""),
        "ambiguous_action": "behavior",
        "business_goal": "intent",
        "business_flow": "flow",
        "ambiguous_flow": "flow",
        "acceptance": "acceptance",
    }
    return aliases.get(category, category)


def canonical_spec_digest(spec: dict[str, Any]) -> str:
    def strip_volatile(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: strip_volatile(item)
                for key, item in sorted(value.items())
                if key not in {"artifact_digest", "command_digest", "generated_at", "generated_from_branch", "generated_from_commit", "updated_at", "permit_id", "producer", "producer_version", "lineage_schema", "input_digests"}
            }
        if isinstance(value, list):
            return [strip_volatile(item) for item in value]
        return value

    payload = json.dumps(strip_volatile(spec), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_question_id(question: dict[str, Any]) -> str:
    identity = "|".join([
        str(question.get("source") or ""),
        str(question.get("category") or ""),
        question_key(question),
    ])
    return f"Q-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:12].upper()}"


def finalize_question_ids(questions: list[dict[str, Any]]) -> None:
    for question in questions:
        question["id"] = stable_question_id(question)
        question.setdefault("answer_provenance", [])


def risk_for_category(category: str) -> str:
    return {
        "business_goal": "Without the real purpose, design may optimize the wrong workflow or solve a symptom instead of the business problem.",
        "business_flow": "Without the end-to-end flow, sequence diagrams, module boundaries, and test cases will become generic or wrong.",
        "actor_entrypoint": "Without the concrete trigger, implementation may modify the wrong UI/API/task/consumer entrypoint.",
        "acceptance": "Without executable acceptance evidence, tests can pass without proving the requirement is satisfied.",
        "state_transition": "Without exact states and triggers, data consistency, rollback, and downstream effects can be incorrect.",
        "ambiguous_action": "Without concrete behavior, scope and implementation can drift into unrelated changes.",
        "ambiguous_flow": "Without source/destination/timing/idempotency, integration and retry behavior can corrupt or duplicate data.",
        "ambiguous_defect": "Without observed/expected behavior and reproduction conditions, the fix may not address the real defect.",
        "ambiguous_scope": "Without scope boundaries, delivery may touch too many systems or miss required scenarios.",
        "ambiguous_rule": "Without exact rules and priority, implementation can encode the wrong default or exception behavior.",
        "ambiguous_exception": "Without exception handling rules, failures may be hidden, retried incorrectly, or exposed to users incorrectly.",
        "ambiguous_state": "Without state ownership and timing, downstream state consumers may observe invalid transitions.",
        "permission": "Without negative permission cases, frontend-only hiding or missing tenant checks can create authorization defects.",
        "data_rule": "Without field definitions and ordering/filter rules, reports, exports, and persistence semantics can be wrong.",
        "api_contract": "Without contract details, consumers may break or compatibility may be guessed.",
        "performance": "Without thresholds, performance risk cannot be tested or accepted.",
        "security": "Without sensitive-field handling, masking, audit, and retention requirements may be missed.",
        "configuration": "Without environment defaults and rollback rules, release behavior can differ across environments.",
        "current_business_state": "Without current-state evidence, design may invent new APIs, jobs, consumers, or data ownership instead of reusing or safely changing existing behavior.",
        "understanding_score": "Without closing weak understanding dimensions, the downstream design can look complete while still missing the real business intent or flow.",
        "business_closure": "Without the business closure chain, sequence diagrams and implementation plans can miss backend services, DB/MQ/cache effects, downstream systems, or user-visible outcomes.",
        "state_machine": "Without state transitions, retry, idempotency, timeout, and compensation rules, asynchronous or stateful changes can corrupt data or leave inconsistent business state.",
        "dependency_chain": "Without upstream/downstream dependency order, multi-system delivery can break contracts, publish messages to the wrong consumers, or miss required integration tests.",
        "repo_impact": "Without concrete repositories and service ownership, cross-repo plans cannot assign implementation, test, release, and rollback responsibilities.",
    }.get(category, "Without this clarification, design and implementation would rely on unapproved assumptions.")


def add_question(questions: list[dict[str, Any]], question: str, owner: str, required: bool, source: str, category: str = "general", risk: str | None = None) -> None:
    if is_placeholder_question(question):
        return
    candidate = {"question": question, "category": category, "source": source}
    if question.lower() in {question_key(item) for item in questions} or semantic_question_key(candidate) in {semantic_question_key(item) for item in questions}:
        return
    questions.append({
        "id": f"Q-{len(questions) + 1}",
        "question": question,
        "owner": owner,
        "required": required,
        "answer": "",
        "status": "open",
        "source": source,
        "category": category,
        "risk_if_unanswered": risk or risk_for_category(category),
    })


def impact_areas(spec: dict[str, Any]) -> set[str]:
    return {str(item.get("area")) for item in as_list(spec.get("impact_surface")) if isinstance(item, dict) and item.get("area")}


def applicability_statuses(spec: dict[str, Any]) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for item in as_list(spec.get("impact_applicability")):
        if not isinstance(item, dict):
            continue
        area = str(item.get("area") or "").strip()
        status = str(item.get("status") or "").strip()
        if area and status:
            statuses[area] = status
    return statuses


def applicable_impact_areas(spec: dict[str, Any]) -> set[str]:
    statuses = applicability_statuses(spec)
    areas = impact_areas(spec)
    if not statuses:
        return areas
    return {area for area in areas if statuses.get(area, "required") != "excluded"}


def is_area_applicable(spec: dict[str, Any], area: str) -> bool:
    return applicability_statuses(spec).get(area, "required") != "excluded"


def entrypoint_question(spec: dict[str, Any]) -> str:
    options = ["frontend actions"]
    if is_area_applicable(spec, "api"):
        options.append("backend APIs")
    options.extend(["scheduled jobs", "MQ consumers", "manual tasks", "external callbacks"])
    if spec_prefers_zh(spec):
        return f"哪些准确入口会触发本次变更，包括{', '.join(options[:-1])}，或 {options[-1]}？"
    return f"Which exact entrypoints trigger the change, including {', '.join(options[:-1])}, or {options[-1]}?"


def current_state_evidence_question(spec: dict[str, Any]) -> str:
    evidence = ["existing frontend routes/actions/components", "source anchors"]
    if is_area_applicable(spec, "api"):
        evidence.append("API contracts")
    if is_area_applicable(spec, "data"):
        evidence.append("persistence/data ownership")
    evidence.extend(["runtime tasks or consumers only when in scope", "downstream dependencies only when in scope"])
    if spec_prefers_zh(spec):
        return f"哪些当前状态证据能证明{', '.join(evidence[:-1])}，以及{evidence[-1]}？"
    return f"Which current-state evidence proves the {', '.join(evidence[:-1])}, and {evidence[-1]}?"


def business_closure_question(spec: dict[str, Any]) -> str:
    nodes = ["actor/external trigger", "frontend UI/component"]
    if is_area_applicable(spec, "api"):
        nodes.append("API")
    nodes.extend(["task/consumer only when in scope", "domain behavior", "visible result"])
    if is_area_applicable(spec, "data"):
        nodes.insert(-1, "persistence/cache")
    if spec_prefers_zh(spec):
        return f"从{' -> '.join(nodes)}的完整业务闭环是什么？"
    return f"What is the full business closure chain from {' through '.join(nodes)}?"


def mentions_excluded_applicability(spec: dict[str, Any], question: dict[str, Any]) -> bool:
    text = f"{question.get('question', '')} {question.get('category', '')} {question.get('source', '')}".lower()
    terms = {
        "api": ("api", "endpoint", "contract", "接口", "端点", "合约"),
        "data": ("data ownership", "data fields", "database", "db", "migration", "persistence", "字段", "数据库", "迁移", "持久化"),
    }
    for area, markers in terms.items():
        if not is_area_applicable(spec, area) and any(marker in text for marker in markers):
            return True
    return False


def merge_existing_answers(
    questions: list[dict[str, Any]],
    existing: dict[str, Any] | None,
    spec: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not existing:
        return questions
    old_digest = str(existing.get("spec_digest") or "")
    existing_questions = [item for item in as_list(existing.get("questions")) if isinstance(item, dict)]
    by_id = {str(item.get("id") or ""): item for item in existing_questions if item.get("id")}
    by_key = {question_key(item): item for item in existing_questions if question_key(item)}
    current_ids = {str(item.get("id") or "") for item in questions}
    merged: list[dict[str, Any]] = []
    for question in questions:
        previous = by_id.get(str(question.get("id") or "")) or by_key.get(question_key(question))
        if previous and previous.get("status") == "closed" and str(previous.get("answer") or "").strip():
            question["status"] = "closed"
            question["answer"] = str(previous["answer"])
            provenance = [item for item in as_list(previous.get("answer_provenance")) if isinstance(item, dict)]
            provenance.append({
                "source": "carried_forward",
                "from_spec_digest": old_digest,
            })
            question["answer_provenance"] = provenance
        merged.append(question)
    for previous in existing_questions:
        previous_id = str(previous.get("id") or stable_question_id(previous))
        if previous_id in current_ids or question_key(previous) in {question_key(item) for item in questions}:
            continue
        if spec is not None and mentions_excluded_applicability(spec, previous):
            continue
        obsolete = dict(previous)
        obsolete["id"] = previous_id
        obsolete["original_required"] = bool(previous.get("required"))
        obsolete["required"] = False
        obsolete["status"] = "obsolete"
        obsolete["obsolete_reason"] = "question no longer generated by the current spec"
        merged.append(obsolete)
    return merged


def generate(spec: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    questions: list[dict[str, Any]] = []
    for item in as_list(spec.get("open_questions")):
        if isinstance(item, dict):
            raw_question = str(item.get("question") or "")
            if is_placeholder_question(raw_question):
                continue
            questions.append({
                "id": item.get("id") or f"Q-{len(questions) + 1}",
                "question": localize_question(raw_question or str(item), str(item.get("category") or "general"), spec),
                "owner": item.get("owner") or "product/engineering",
                "required": True,
                "answer": item.get("answer", ""),
                "status": item.get("status", "open"),
                "source": "spec.open_questions",
                "category": item.get("category", "general"),
                "risk_if_unanswered": item.get("risk_if_unanswered") or risk_for_category(str(item.get("category") or "general")),
            })
    for conflict in as_list(spec.get("rule_conflicts")):
        if isinstance(conflict, dict):
            add_question(questions, f"Resolve rule conflict: {conflict.get('message')}", "product/engineering", True, "spec.rule_conflicts", "business_rule")
    understanding = as_dict(spec.get("requirements_understanding"))
    for ambiguity in as_list(spec.get("ambiguities")) + as_list(understanding.get("blockers")):
        if not isinstance(ambiguity, dict):
            continue
        if ambiguity.get("required") is False:
            continue
        category = str(ambiguity.get("category") or "ambiguity")
        message = str(ambiguity.get("message") or "")
        if not message:
            continue
        question_text = {
            "business_goal": "What is the real business purpose, current pain point, affected users, and expected measurable outcome for this requirement?",
            "business_flow": "What is the complete business flow: actor, precondition, entry point, trigger, system behavior, success result, and failure handling?",
            "actor_entrypoint": entrypoint_question(spec),
            "acceptance": "What concrete, executable acceptance criteria prove this requirement is satisfied, including evidence to collect?",
            "state_transition": "What are the exact from/to states, trigger timing, and invalid state transitions?",
            "ambiguous_action": "What concrete behavior change is required, and what existing behavior must remain unchanged?",
            "ambiguous_flow": "What source, destination, trigger timing, retry, idempotency, and completion condition define this flow?",
            "ambiguous_defect": "What is the observed defect, expected behavior, affected data/users, and reproduction or detection condition?",
            "ambiguous_scope": "Which objects, users, systems, and scenarios are in scope and explicitly out of scope?",
            "ambiguous_rule": "What exact rule, default value, priority, exception, and rollback behavior should apply?",
            "ambiguous_exception": "Which exception cases must be handled, ignored, retried, or surfaced to users/operators?",
            "ambiguous_state": "Which state should be updated, when, by whom, and what downstream effects are expected?",
            "business_closure": business_closure_question(spec),
            "state_machine": "What are the exact state transitions, triggers, retry policy, idempotency key, timeout rule, compensation rule, and invalid transitions?",
            "dependency_chain": "What are the ordered upstream and downstream systems, message topics, API contracts, consumers, and integration evidence required?",
            "repo_impact": "Which repositories/services own each part of this requirement, and which are one-degree or multi-degree dependencies?",
        }.get(category, f"Clarify requirement ambiguity: {message}")
        add_question(questions, question_text, "product/engineering", True, f"ambiguity.{ambiguity.get('source', category)}", category, risk_for_category(category))
    scorecard = as_dict(understanding.get("scorecard"))
    weak_dimensions = as_list(scorecard.get("weak_dimensions")) + as_list(understanding.get("weak_dimensions"))
    score_questions = {
        "intent_score": "What real business purpose, current pain point, target users, and measurable success signal should this requirement satisfy?",
        "flow_score": "What are the complete success, failure, permission, retry, timeout, idempotency, and compensation branches in the business flow?",
        "entrypoint_score": entrypoint_question(spec),
        "acceptance_score": "Which executable positive and negative acceptance cases prove every business branch is satisfied?",
        "evidence_score": current_state_evidence_question(spec),
        "closure_score": business_closure_question(spec),
        "state_score": "What state machine, retry, idempotency, timeout, and compensation rules govern this requirement?",
        "dependency_score": "What ordered dependency chain and repository/service ownership prove the multi-system plan?",
        "runtime_dependency_score": "What runtime dependency graph proves API-to-service, service-to-DB, producer-to-topic, topic-to-consumer, and downstream interactions with source evidence?",
    }
    for dimension in sorted({str(item) for item in weak_dimensions if item}):
        question_text = score_questions.get(dimension, "")
        if question_text:
            add_question(questions, question_text, "product/engineering", True, f"requirements_understanding.{dimension}", "understanding_score")
    for advisory in as_list(as_dict(spec.get("business_goal_quality")).get("advisories")):
        if isinstance(advisory, dict) and advisory.get("source") == "measurable_metric":
            add_question(questions, "What quantitative success threshold should be observed for this requirement?", "product/engineering", False, "business_goal_quality.measurable_metric", "success_metric")
    current_state = as_dict(spec.get("current_business_state"))
    for gap in as_list(current_state.get("evidence_gaps")):
        if isinstance(gap, dict) and gap.get("message"):
            add_question(
                questions,
                current_state_evidence_question(spec),
                "engineering",
                False,
                "current_business_state.evidence_gaps",
                "current_business_state",
            )
    state_machine = as_dict(spec.get("state_machine"))
    if state_machine.get("missing"):
        add_question(
            questions,
            "What state transitions, retry policy, idempotency key, timeout rule, compensation rule, and invalid transitions are required?",
            "product/engineering",
            True,
            "state_machine.missing",
            "state_machine",
        )
    closure = as_dict(spec.get("business_closure_model"))
    if closure.get("missing_nodes"):
            add_question(
                questions,
                business_closure_question(spec),
            "engineering/product",
            True,
            "business_closure_model.missing_nodes",
            "business_closure",
        )
    dependency_chain = as_dict(spec.get("dependency_chain"))
    if dependency_chain.get("missing"):
        add_question(
            questions,
            "What ordered upstream/downstream dependency chain, message topics, API contracts, and repository ownership must be followed?",
            "engineering",
            True,
            "dependency_chain.missing",
            "dependency_chain",
        )
    repo_impact = as_dict(spec.get("repo_impact_map"))
    if repo_impact.get("missing_repo_evidence"):
        add_question(
            questions,
            "Which repositories and services are owner, upstream, downstream, or confirm-only dependencies for this requirement?",
            "engineering",
            True,
            "repo_impact_map.missing_repo_evidence",
            "repo_impact",
        )
    if not as_list(spec.get("acceptance_criteria")):
        add_question(questions, "What are the acceptance criteria and evidence required?", "product", True, "missing.acceptance_criteria", "acceptance")
    if as_list(spec.get("acceptance_criteria")) and all(not str(item.get("source_evidence") or "").startswith("input") for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)):
        add_question(questions, "Confirm concrete, testable acceptance criteria; current acceptance was inferred from the request.", "product", True, "quality.inferred_acceptance", "acceptance")
    scope = as_dict(spec.get("scope"))
    if not as_list(scope.get("out_of_scope")):
        add_question(questions, "What is explicitly out of scope for this change?", "product/engineering", False, "missing.out_of_scope", "scope_boundary")
    for constraint in as_list(spec.get("implicit_constraints")):
        if isinstance(constraint, dict) and constraint.get("status") == "requires_confirmation" and constraint.get("question"):
            area = str(constraint.get("area") or "")
            if area and not is_area_applicable(spec, area):
                continue
            add_question(questions, str(constraint["question"]), "product/engineering", True, f"implicit.{constraint.get('area', 'constraint')}", str(constraint.get("area") or "implicit_constraint"))
    areas = applicable_impact_areas(spec)
    if "permission" in areas and not as_list(spec.get("negative_acceptance_criteria")):
        add_question(questions, "Which unauthorized roles, tenant/data-scope cases, and negative permission tests must fail?", "product/security", True, "impact.permission", "permission")
    if "data" in areas and not as_list(spec.get("data_fields")):
        add_question(questions, "Which data fields, definitions, filters, null/default rules, and export ordering are required?", "product/data-owner", True, "impact.data", "data_rule")
    if "api" in areas:
        add_question(questions, "Which endpoint, request/response fields, error codes, compatibility rules, and old consumers are in scope?", "engineering", True, "impact.api", "api_contract")
    if "performance" in areas:
        add_question(questions, "What latency, throughput, batch size, export volume, and performance evidence thresholds are required?", "product/engineering", True, "impact.performance", "performance")
    if "security" in areas:
        add_question(questions, "Which sensitive fields require masking, authorization checks, audit logs, retention limits, or privacy review?", "security/product", True, "impact.security", "security")
    if "config" in areas:
        add_question(questions, "What are the configuration defaults, environment overrides, rollout scope, and rollback behavior?", "engineering/release", True, "impact.config", "configuration")
    for question in questions:
        if isinstance(question, dict):
            question["question"] = localize_question(
                str(question.get("question") or ""),
                str(question.get("category") or "general"),
                spec,
            )
    finalize_question_ids(questions)
    questions = merge_existing_answers(questions, existing, spec)
    decision = "block" if any(q["required"] and q["status"] != "closed" for q in questions) else "pass"
    return {
        "schema": SCHEMA,
        "doc_id": spec.get("doc_id"),
        "spec_schema": spec.get("schema", ""),
        "spec_digest": canonical_spec_digest(spec),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "questions": questions,
        "decision": decision,
    }


def validate_questions(data: dict[str, Any], spec: dict[str, Any] | None = None) -> dict[str, Any]:
    blockers = []
    if data.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    if spec is not None:
        expected_digest = canonical_spec_digest(spec)
        if data.get("spec_digest") != expected_digest:
            blockers.append({"source": "spec_digest", "message": "open questions were not generated from the current spec"})
    for question in as_list(data.get("questions")):
        question_text = str(question.get("question") or "") if isinstance(question, dict) else ""
        if isinstance(question, dict) and "question" in question and is_placeholder_question(question_text):
            blockers.append({"source": question.get("id", "question"), "message": "question is a placeholder and must be regenerated"})
        if (
            isinstance(question, dict)
            and spec is not None
            and spec_prefers_zh(spec)
            and not has_cjk(question_text)
            and question_text.lower().startswith(ENGLISH_TEMPLATE_PREFIXES)
        ):
            blockers.append({"source": question.get("id", "question"), "message": "Chinese requirement generated an English template question"})
        if isinstance(question, dict) and question.get("required") and question.get("status") != "closed":
            blockers.append({"source": question.get("id", "question"), "message": "required question is not closed"})
        if isinstance(question, dict) and question.get("required") and question.get("status") == "closed" and not str(question.get("answer") or "").strip():
            blockers.append({"source": question.get("id", "question"), "message": "required closed question must include an answer"})
        if isinstance(question, dict) and question.get("required") and not str(question.get("risk_if_unanswered") or "").strip():
            blockers.append({"source": question.get("id", "question"), "message": "required question must include risk_if_unanswered"})
    return {"schema": "codex-open-questions-validation-v1", "decision": "block" if blockers else "pass", "blockers": blockers}


def refresh_decision(data: dict[str, Any]) -> str:
    blocked = any(
        isinstance(question, dict)
        and question.get("required")
        and (
            question.get("status") != "closed"
            or not str(question.get("answer") or "").strip()
        )
        for question in as_list(data.get("questions"))
    )
    data["decision"] = "block" if blocked else "pass"
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    return str(data["decision"])


def clarification_label(question: dict[str, Any]) -> str:
    category = str(question.get("category") or "").lower()
    source = str(question.get("source") or "").lower()
    if category in {"business_goal", "success_metric"} or "intent" in source:
        return "Goal"
    if category in {"business_flow", "ambiguous_flow", "business_closure"} or "flow" in source:
        return "Flow"
    if category == "actor_entrypoint" or "entrypoint" in source:
        return "Entrypoint"
    if category == "acceptance" or "acceptance" in source:
        return "AC"
    if category in {"state_transition", "ambiguous_state", "state_machine"}:
        return "State transition"
    if category in {"ambiguous_scope", "scope_boundary", "repo_impact"}:
        return "Scope"
    return "Requirement clarification"


def render_clarification_answers(data: dict[str, Any]) -> str:
    lines = [
        "# Requirement Clarification Answers",
        "",
        f"- Doc ID: {data.get('doc_id') or ''}",
        f"- Question schema: {data.get('schema') or ''}",
        f"- Spec digest: {data.get('spec_digest') or ''}",
        "",
    ]
    for question in as_list(data.get("questions")):
        if not isinstance(question, dict) or question.get("status") != "closed":
            continue
        answer = str(question.get("answer") or "").strip()
        if not answer:
            continue
        lines.extend([
            f"## {question.get('id') or 'Question'}",
            "",
            f"- Category: {question.get('category') or 'general'}",
            f"- Owner: {question.get('owner') or ''}",
            f"- Answered question: {question.get('question') or ''}",
            "",
            f"{clarification_label(question)}: {answer}",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def answer_interactively(
    data: dict[str, Any],
    spec: dict[str, Any],
    persist_fn: Callable[[dict[str, Any]], None],
    *,
    actor: str,
    include_optional: bool = False,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> dict[str, Any]:
    preflight_blockers: list[dict[str, Any]] = []
    if data.get("schema") != SCHEMA:
        preflight_blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    if data.get("spec_digest") != canonical_spec_digest(spec):
        preflight_blockers.append({"source": "spec_digest", "message": "open questions were not generated from the current spec"})
    if preflight_blockers:
        return {"decision": "block", "blockers": preflight_blockers, "answered": 0, "remaining": 0}

    pending = [
        question
        for question in as_list(data.get("questions"))
        if isinstance(question, dict)
        and question.get("status") == "open"
        and (question.get("required") or include_optional)
    ]
    answered = 0
    interrupted = False
    output_fn(f"Requirement clarification: {len(pending)} question(s) to answer.")
    for index, question in enumerate(pending, start=1):
        output_fn("")
        output_fn(f"[{index}/{len(pending)}] {question.get('id')} | {question.get('category', 'general')} | owner: {question.get('owner', '')}")
        output_fn(str(question.get("question") or ""))
        output_fn(f"Risk if unanswered: {question.get('risk_if_unanswered') or ''}")
        while True:
            try:
                answer = input_fn("Answer: ").strip()
            except (EOFError, KeyboardInterrupt):
                interrupted = True
                output_fn("\nClarification interrupted; completed answers were preserved.")
                break
            if answer or not question.get("required"):
                break
            output_fn("A required question needs a non-empty answer. Please answer before continuing.")
        if interrupted:
            break
        if not answer:
            continue
        answered_at = datetime.now(timezone.utc).isoformat()
        question["answer"] = answer
        question["status"] = "closed"
        question["answered_at"] = answered_at
        question["answered_by"] = actor
        provenance = [item for item in as_list(question.get("answer_provenance")) if isinstance(item, dict)]
        provenance.append({"source": "interactive_cli", "actor": actor, "answered_at": answered_at})
        question["answer_provenance"] = provenance
        answered += 1
        refresh_decision(data)
        persist_fn(data)
        output_fn("Answer saved.")

    refresh_decision(data)
    persist_fn(data)
    remaining = sum(
        1
        for question in as_list(data.get("questions"))
        if isinstance(question, dict) and question.get("required") and question.get("status") != "closed"
    )
    return {
        "decision": "block" if interrupted or remaining else "pass",
        "blockers": ([{"source": "interactive_input", "message": "clarification was interrupted"}] if interrupted else []),
        "answered": answered,
        "remaining": remaining,
        "interrupted": interrupted,
    }


def answer_file_interactively(
    questions_path: Path,
    spec_path: Path,
    out_path: Path,
    *,
    actor: str,
    include_optional: bool = False,
    input_fn: Callable[[str], str] = input,
    output_fn: Callable[[str], None] = print,
) -> dict[str, Any]:
    data = load_json(questions_path)
    spec = load_json(spec_path)

    def persist(current: dict[str, Any]) -> None:
        write_json(questions_path, current)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render_clarification_answers(current), encoding="utf-8")

    return answer_interactively(
        data,
        spec,
        persist,
        actor=actor,
        include_optional=include_optional,
        input_fn=input_fn,
        output_fn=output_fn,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate, answer, or validate open requirement questions")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_gen = sub.add_parser("generate")
    p_gen.add_argument("--spec", required=True)
    p_gen.add_argument("--out", required=True)
    p_val = sub.add_parser("validate")
    p_val.add_argument("--file", required=True)
    p_val.add_argument("--spec")
    p_val.add_argument("--out")
    p_answer = sub.add_parser("answer")
    p_answer.add_argument("--file", required=True)
    p_answer.add_argument("--spec", required=True)
    p_answer.add_argument("--out")
    p_answer.add_argument("--actor", default="")
    p_answer.add_argument("--include-optional", action="store_true")
    args = parser.parse_args()
    if args.cmd == "generate":
        out_path = Path(args.out)
        existing = load_json(out_path) if out_path.exists() else None
        result = generate(load_json(Path(args.spec)), existing)
        write_json(out_path, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        # Generation records unresolved questions as an artifact; validation and workflow gates
        # decide whether they block approval or implementation.
        return 0
    if args.cmd == "answer":
        if not sys.stdin.isatty():
            print("Interactive clarification requires a TTY; run this command in a terminal.", file=sys.stderr)
            return 2
        questions_path = Path(args.file)
        out_path = Path(args.out) if args.out else questions_path.with_name("clarification_answers.md")
        result = answer_file_interactively(
            questions_path,
            Path(args.spec),
            out_path,
            actor=args.actor.strip() or getpass.getuser() or "interactive_user",
            include_optional=args.include_optional,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["decision"] == "pass" else 2
    result = validate_questions(load_json(Path(args.file)), load_json(Path(args.spec)) if args.spec else None)
    if args.out:
        write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
