#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-open-questions-v1"


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


def question_key(question: dict[str, Any]) -> str:
    return str(question.get("question") or "").strip().lower()


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
    }.get(category, "Without this clarification, design and implementation would rely on unapproved assumptions.")


def add_question(questions: list[dict[str, Any]], question: str, owner: str, required: bool, source: str, category: str = "general", risk: str | None = None) -> None:
    if question.lower() in {question_key(item) for item in questions}:
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


def generate(spec: dict[str, Any]) -> dict[str, Any]:
    questions: list[dict[str, Any]] = []
    for item in as_list(spec.get("open_questions")):
        if isinstance(item, dict):
            questions.append({
                "id": item.get("id") or f"Q-{len(questions) + 1}",
                "question": item.get("question") or str(item),
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
    understanding = spec.get("requirements_understanding") if isinstance(spec.get("requirements_understanding"), dict) else {}
    for ambiguity in as_list(spec.get("ambiguities")) + as_list(understanding.get("blockers")):
        if not isinstance(ambiguity, dict):
            continue
        category = str(ambiguity.get("category") or "ambiguity")
        message = str(ambiguity.get("message") or "")
        if not message:
            continue
        question_text = {
            "business_goal": "What is the real business purpose, current pain point, affected users, and expected measurable outcome for this requirement?",
            "business_flow": "What is the complete business flow: actor, precondition, entry point, trigger, system behavior, success result, and failure handling?",
            "actor_entrypoint": "Which concrete entry point triggers this requirement: frontend operation, backend API, MQ consumer, scheduled job, manual task, batch script, or external callback?",
            "acceptance": "What concrete, executable acceptance criteria prove this requirement is satisfied, including evidence to collect?",
            "state_transition": "What are the exact from/to states, trigger timing, and invalid state transitions?",
            "ambiguous_action": "What concrete behavior change is required, and what existing behavior must remain unchanged?",
            "ambiguous_flow": "What source, destination, trigger timing, retry, idempotency, and completion condition define this flow?",
            "ambiguous_defect": "What is the observed defect, expected behavior, affected data/users, and reproduction or detection condition?",
            "ambiguous_scope": "Which objects, users, systems, and scenarios are in scope and explicitly out of scope?",
            "ambiguous_rule": "What exact rule, default value, priority, exception, and rollback behavior should apply?",
            "ambiguous_exception": "Which exception cases must be handled, ignored, retried, or surfaced to users/operators?",
            "ambiguous_state": "Which state should be updated, when, by whom, and what downstream effects are expected?",
        }.get(category, f"Clarify requirement ambiguity: {message}")
        add_question(questions, question_text, "product/engineering", True, f"ambiguity.{ambiguity.get('source', category)}", category, risk_for_category(category))
    scorecard = understanding.get("scorecard") if isinstance(understanding.get("scorecard"), dict) else {}
    weak_dimensions = as_list(scorecard.get("weak_dimensions")) + as_list(understanding.get("weak_dimensions"))
    score_questions = {
        "intent_score": "What real business purpose, current pain point, target users, and measurable success signal should this requirement satisfy?",
        "flow_score": "What are the complete success, failure, permission, retry, timeout, idempotency, and compensation branches in the business flow?",
        "entrypoint_score": "Which exact entrypoints trigger the change, including frontend actions, backend APIs, scheduled jobs, MQ consumers, manual tasks, or external callbacks?",
        "acceptance_score": "Which executable positive and negative acceptance cases prove every business branch is satisfied?",
        "evidence_score": "Which current-state evidence proves the existing entrypoints, APIs, tasks, consumers, data ownership, and downstream dependencies?",
    }
    for dimension in sorted({str(item) for item in weak_dimensions if item}):
        question_text = score_questions.get(dimension)
        if question_text:
            add_question(questions, question_text, "product/engineering", True, f"requirements_understanding.{dimension}", "understanding_score")
    current_state = spec.get("current_business_state") if isinstance(spec.get("current_business_state"), dict) else {}
    for gap in as_list(current_state.get("evidence_gaps")):
        if isinstance(gap, dict) and gap.get("message"):
            add_question(
                questions,
                "What current implementation evidence describes the existing entrypoints, APIs, jobs, consumers, data ownership, and downstream dependencies?",
                "engineering",
                False,
                "current_business_state.evidence_gaps",
                "current_business_state",
            )
    if not as_list(spec.get("acceptance_criteria")):
        add_question(questions, "What are the acceptance criteria and evidence required?", "product", True, "missing.acceptance_criteria", "acceptance")
    if as_list(spec.get("acceptance_criteria")) and all(str(item.get("source_evidence")) != "input" for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)):
        add_question(questions, "Confirm concrete, testable acceptance criteria; current acceptance was inferred from the request.", "product", True, "quality.inferred_acceptance", "acceptance")
    scope = spec.get("scope") if isinstance(spec.get("scope"), dict) else {}
    if not as_list(scope.get("out_of_scope")):
        add_question(questions, "What is explicitly out of scope for this change?", "product/engineering", False, "missing.out_of_scope", "scope_boundary")
    for constraint in as_list(spec.get("implicit_constraints")):
        if isinstance(constraint, dict) and constraint.get("status") == "requires_confirmation" and constraint.get("question"):
            add_question(questions, str(constraint["question"]), "product/engineering", True, f"implicit.{constraint.get('area', 'constraint')}", str(constraint.get("area") or "implicit_constraint"))
    areas = impact_areas(spec)
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
    decision = "block" if any(q["required"] and q["status"] != "closed" for q in questions) else "pass"
    return {"schema": SCHEMA, "doc_id": spec.get("doc_id"), "questions": questions, "decision": decision}


def validate_questions(data: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    if data.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    for question in as_list(data.get("questions")):
        if isinstance(question, dict) and question.get("required") and question.get("status") != "closed":
            blockers.append({"source": question.get("id", "question"), "message": "required question is not closed"})
        if isinstance(question, dict) and question.get("required") and question.get("status") == "closed" and not str(question.get("answer") or "").strip():
            blockers.append({"source": question.get("id", "question"), "message": "required closed question must include an answer"})
        if isinstance(question, dict) and question.get("required") and not str(question.get("risk_if_unanswered") or "").strip():
            blockers.append({"source": question.get("id", "question"), "message": "required question must include risk_if_unanswered"})
    return {"schema": "codex-open-questions-validation-v1", "decision": "block" if blockers else "pass", "blockers": blockers}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate open requirement questions")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_gen = sub.add_parser("generate")
    p_gen.add_argument("--spec", required=True)
    p_gen.add_argument("--out", required=True)
    p_val = sub.add_parser("validate")
    p_val.add_argument("--file", required=True)
    p_val.add_argument("--out")
    args = parser.parse_args()
    if args.cmd == "generate":
        result = generate(load_json(Path(args.spec)))
        write_json(Path(args.out), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["decision"] == "pass" else 1
    result = validate_questions(load_json(Path(args.file)))
    if args.out:
        write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
