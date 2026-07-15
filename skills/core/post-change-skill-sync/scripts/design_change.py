#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA = "codex-design-change-v1"


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def template(doc_id: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "doc_id": doc_id, "decision": "draft", "discovery": "", "previous_design": [], "new_design": [], "decision_reason": "", "scope_changes": [], "acceptance_changes": [], "diagram_changes": [], "test_changes": [], "approvals": []}


def validate(data: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, str]] = []
    if data.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    for key in ("doc_id", "discovery", "decision_reason"):
        if not str(data.get(key) or "").strip():
            blockers.append({"source": key, "message": f"{key} is required"})
    if not data.get("previous_design") or not data.get("new_design"):
        blockers.append({"source": "design_delta", "message": "previous_design and new_design are required"})
    if not data.get("acceptance_changes") or not data.get("test_changes"):
        blockers.append({"source": "traceability", "message": "acceptance_changes and test_changes are required"})
    if data.get("decision") in {"approved", "pass"} and not data.get("approvals"):
        blockers.append({"source": "approvals", "message": "approved design change requires approval evidence"})
    return {"schema": "codex-design-change-validation-v1", "decision": "block" if blockers else "pass", "blockers": blockers}


def write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or validate controlled design-change evidence")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("template")
    create.add_argument("--doc-id", required=True)
    create.add_argument("--out", required=True)
    check = sub.add_parser("validate")
    check.add_argument("--file", required=True)
    check.add_argument("--out")
    args = parser.parse_args()
    if args.command == "template":
        result = template(args.doc_id)
        write(Path(args.out), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    result = validate(load_json(Path(args.file)))
    if args.out:
        write(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
