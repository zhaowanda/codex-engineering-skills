#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-data-model-design-v1"


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


def design(spec: dict[str, Any], technical: dict[str, Any] | None = None) -> dict[str, Any]:
    technical = technical or {}
    model = technical.get("data_model_design") if isinstance(technical.get("data_model_design"), dict) else {}
    if model.get("applicable") is False:
        return {"schema": SCHEMA, "decision": "not_applicable", "applicable": False, "blockers": []}
    applicable = bool(model.get("applicable")) or any(str(item.get("area") or "") in {"data", "database"} for item in as_list(spec.get("impact_surface")) if isinstance(item, dict))
    if not applicable:
        return {"schema": SCHEMA, "decision": "not_applicable", "applicable": False, "blockers": []}
    tables = as_list(model.get("tables")) or as_list(technical.get("table_schema_changes"))
    blockers = []
    if any(isinstance(item, dict) and "needs_confirmation" in json.dumps(item, ensure_ascii=False).lower() for item in tables):
        blockers.append({"source": "data_model", "message": "Table, field type, nullable/default, or index details need source confirmation before schema migration."})
    return {
        "schema": SCHEMA,
        "doc_id": spec.get("doc_id") or technical.get("doc_id"),
        "title": spec.get("title") or technical.get("title"),
        "decision": "block" if blockers else "pass",
        "applicable": True,
        "business_objects": model.get("business_objects") or spec.get("business_objects") or [],
        "tables": tables,
        "field_rules": model.get("field_rules") or model.get("fields") or [],
        "ownership": model.get("ownership") or "data owner must be confirmed from project evidence",
        "read_write_rules": model.get("read_write_rules") or {},
        "indexes": model.get("indexes") or [],
        "migration_strategy": model.get("migration_strategy") or "record no-migration evidence or provide forward/backward migration",
        "history_data_strategy": model.get("history_data_strategy") or "cover old rows, null/default semantics, and backfill scope",
        "rollback_strategy": model.get("rollback_strategy") or "code rollback plus data compatibility/rollback plan",
        "test_data_requirements": ["new data", "old data", "null/default data", "permission-scoped data"],
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate data model design")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--technical-design")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = design(load_json(Path(args.spec)), load_json(Path(args.technical_design)) if args.technical_design else {})
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") in {"pass", "not_applicable"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
