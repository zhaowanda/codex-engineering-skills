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
            })
    if not as_list(spec.get("acceptance_criteria")):
        questions.append({"id": f"Q-{len(questions) + 1}", "question": "What are the acceptance criteria and evidence required?", "owner": "product", "required": True, "answer": "", "status": "open"})
    scope = spec.get("scope") if isinstance(spec.get("scope"), dict) else {}
    if not as_list(scope.get("out_of_scope")):
        questions.append({"id": f"Q-{len(questions) + 1}", "question": "What is explicitly out of scope for this change?", "owner": "product/engineering", "required": False, "answer": "", "status": "open"})
    decision = "block" if any(q["required"] and q["status"] != "closed" for q in questions) else "pass"
    return {"schema": SCHEMA, "doc_id": spec.get("doc_id"), "questions": questions, "decision": decision}


def validate_questions(data: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    if data.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    for question in as_list(data.get("questions")):
        if isinstance(question, dict) and question.get("required") and question.get("status") != "closed":
            blockers.append({"source": question.get("id", "question"), "message": "required question is not closed"})
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
