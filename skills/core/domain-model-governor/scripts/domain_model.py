#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-domain-model-design-v1"


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


def design(spec: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    understanding = spec.get("requirements_understanding") if isinstance(spec.get("requirements_understanding"), dict) else {}
    business_intent = spec.get("business_intent") or understanding.get("business_intent") or ""
    business_flow = spec.get("business_flow") or understanding.get("business_flow") or []
    if not business_intent:
        blockers.append({"source": "business_intent", "message": "Business purpose is missing or ambiguous."})
    if not business_flow:
        blockers.append({"source": "business_flow", "message": "Business flow is missing; clarify actor, trigger, action, and completion."})
    objects = as_list(spec.get("business_objects")) or [{"name": "affected business object", "source": "requirement"}]
    transitions = as_list(spec.get("state_transitions")) or as_list((understanding.get("state_machine") or {}).get("transitions")) if isinstance(understanding.get("state_machine"), dict) else []
    rules = as_list(spec.get("business_rules"))
    return {
        "schema": SCHEMA,
        "doc_id": spec.get("doc_id"),
        "title": spec.get("title"),
        "decision": "block" if blockers else "pass",
        "business_intent": business_intent,
        "business_flow": business_flow,
        "business_objects": objects,
        "lifecycle": [{"object": item.get("name") if isinstance(item, dict) else str(item), "states": ["current", "target"], "owner": "business owner/source of truth must be confirmed"} for item in objects],
        "state_machine": {"transitions": transitions, "missing_transition_policy": "block implementation if from/to state or trigger is unclear"},
        "invariants": ["permission/data-scope boundaries remain valid", "state transitions must be idempotent or protected from duplicate execution", "business completion condition must map to acceptance evidence"],
        "rules": rules,
        "trigger_conditions": spec.get("trigger_conditions") or understanding.get("trigger_conditions") or [],
        "preconditions": spec.get("preconditions") or understanding.get("preconditions") or [],
        "postconditions": spec.get("postconditions") or understanding.get("postconditions") or [],
        "exception_paths": ["invalid input", "permission denied", "duplicate operation", "dependency failure", "partial completion"],
        "clarification_questions": [item.get("question") if isinstance(item, dict) else str(item) for item in as_list(spec.get("open_questions"))],
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate domain model design")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = design(load_json(Path(args.spec)))
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
