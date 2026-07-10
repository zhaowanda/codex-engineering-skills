#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-api-contract-design-v1"
API_TERMS = ("api", "endpoint", "route", "接口", "调用", "服务", "contract")


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def has_signal(spec: dict[str, Any], technical: dict[str, Any]) -> bool:
    impacts = {str(item.get("area") or "").lower() for item in as_list(spec.get("impact_surface")) if isinstance(item, dict)}
    text = json.dumps([spec, technical.get("api_contracts"), technical.get("system_interaction_sequence")], ensure_ascii=False).lower()
    return "api" in impacts or any(term in text for term in API_TERMS)


def design(spec: dict[str, Any], technical: dict[str, Any] | None = None, architecture_framing: dict[str, Any] | None = None) -> dict[str, Any]:
    technical = technical or {}
    architecture_framing = architecture_framing or {}
    if not has_signal(spec, technical) and not architecture_framing.get("provider_consumer"):
        return {"schema": SCHEMA, "decision": "not_applicable", "applicable": False, "blockers": []}
    blockers: list[dict[str, str]] = []
    raw_contracts = [item for item in as_list(technical.get("api_contracts")) if isinstance(item, dict)]
    framing_contracts = [
        {"contract": item.get("contract"), "compatibility": "must preserve provider/consumer compatibility", "old_consumer_impact": f"consumer: {item.get('consumer')}"}
        for item in as_list(architecture_framing.get("provider_consumer"))
        if isinstance(item, dict) and item.get("contract")
    ]
    contracts: list[dict[str, Any]] = []
    for item in raw_contracts or framing_contracts or [{"contract": "api path/method must be confirmed"}]:
        name = str(item.get("contract") or item.get("api") or "")
        if "no api impact" in name.lower() and "confirm" not in str(item.get("api_impact") or "").lower():
            continue
        method = "GET" if any(token in name.upper() for token in ["GET ", "QUERY", "LIST"]) else "POST"
        if "must be confirmed" in name.lower() or "no api impact confirmed" in name.lower() or not name:
            blockers.append({"source": "api_contract", "message": "API contract name/path is not concrete."})
        contracts.append({
            "name": name or "api path/method must be confirmed",
            "method": method,
            "path": name if "/" in name else "path must be confirmed",
            "owner": (technical.get("project_context") or {}).get("project") if isinstance(technical.get("project_context"), dict) else "owner must be confirmed",
            "request": {"path_params": [], "query": ["filters/sort/page when list query is involved"], "body": ["business fields required by requirement"]},
            "response": {"success": ["business result fields"], "error": ["code", "message", "trace_id"]},
            "permission": "server-side authorization is authoritative",
            "idempotency": "required for write/retry operations; use request id or business id",
            "compatibility": item.get("compatibility") or "additive by default; breaking changes require consumer migration",
            "consumer_impact": item.get("old_consumer_impact") or "review existing consumers before implementation",
        })
    if not contracts:
        blockers.append({"source": "api_contract", "message": "API signal exists but no concrete reused or changed contract is documented."})
    return {
        "schema": SCHEMA,
        "doc_id": spec.get("doc_id") or technical.get("doc_id"),
        "title": spec.get("title") or technical.get("title"),
        "decision": "block" if blockers else "pass",
        "applicable": True,
        "contracts": contracts,
        "compatibility": ["old consumers keep working", "new fields are additive unless explicitly approved", "errors remain machine-readable"],
        "consumer_impact": ["frontend callers", "backend/service consumers", "tests and documentation"],
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate API contract design")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--technical-design")
    parser.add_argument("--architecture-framing")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = design(
        load_json(Path(args.spec)),
        load_json(Path(args.technical_design)) if args.technical_design else {},
        load_json(Path(args.architecture_framing)) if args.architecture_framing else {},
    )
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") in {"pass", "not_applicable"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
