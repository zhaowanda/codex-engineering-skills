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


def add_question(questions: list[dict[str, Any]], question: str, owner: str, required: bool, source: str) -> None:
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
            })
    for conflict in as_list(spec.get("rule_conflicts")):
        if isinstance(conflict, dict):
            add_question(questions, f"Resolve rule conflict: {conflict.get('message')}", "product/engineering", True, "spec.rule_conflicts")
    if not as_list(spec.get("acceptance_criteria")):
        add_question(questions, "What are the acceptance criteria and evidence required?", "product", True, "missing.acceptance_criteria")
    if as_list(spec.get("acceptance_criteria")) and all(str(item.get("source_evidence")) != "input" for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)):
        add_question(questions, "Confirm concrete, testable acceptance criteria; current acceptance was inferred from the request.", "product", True, "quality.inferred_acceptance")
    scope = spec.get("scope") if isinstance(spec.get("scope"), dict) else {}
    if not as_list(scope.get("out_of_scope")):
        add_question(questions, "What is explicitly out of scope for this change?", "product/engineering", False, "missing.out_of_scope")
    for constraint in as_list(spec.get("implicit_constraints")):
        if isinstance(constraint, dict) and constraint.get("status") == "requires_confirmation" and constraint.get("question"):
            add_question(questions, str(constraint["question"]), "product/engineering", True, f"implicit.{constraint.get('area', 'constraint')}")
    areas = impact_areas(spec)
    if "permission" in areas and not as_list(spec.get("negative_acceptance_criteria")):
        add_question(questions, "Which unauthorized roles, tenant/data-scope cases, and negative permission tests must fail?", "product/security", True, "impact.permission")
    if "data" in areas and not as_list(spec.get("data_fields")):
        add_question(questions, "Which data fields, definitions, filters, null/default rules, and export ordering are required?", "product/data-owner", True, "impact.data")
    if "api" in areas:
        add_question(questions, "Which endpoint, request/response fields, error codes, compatibility rules, and old consumers are in scope?", "engineering", True, "impact.api")
    if "performance" in areas:
        add_question(questions, "What latency, throughput, batch size, export volume, and performance evidence thresholds are required?", "product/engineering", True, "impact.performance")
    if "security" in areas:
        add_question(questions, "Which sensitive fields require masking, authorization checks, audit logs, retention limits, or privacy review?", "security/product", True, "impact.security")
    if "config" in areas:
        add_question(questions, "What are the configuration defaults, environment overrides, rollout scope, and rollback behavior?", "engineering/release", True, "impact.config")
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
