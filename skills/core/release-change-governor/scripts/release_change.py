#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


SCHEMA = "codex-release-change-v1"


def template() -> dict:
    return {
        "schema": SCHEMA,
        "decision": "pending",
        "change_ticket": "",
        "risk_level": "",
        "release_window": {"start": "", "end": "", "timezone": ""},
        "approvers": [],
        "implementers": [],
        "approval_audit": {},
        "integration_evidence": {},
        "release_order": [],
        "rollback_plan": [],
        "rollback_owner": "",
        "communication_plan": [],
        "post_release_checks": [],
    }


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate(data: dict) -> dict:
    blockers = []
    if data.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    for key in ["change_ticket", "risk_level", "approvers", "release_order", "rollback_plan", "rollback_owner", "post_release_checks"]:
        if not data.get(key):
            blockers.append({"source": key, "message": f"{key} is required"})
    window = data.get("release_window") if isinstance(data.get("release_window"), dict) else {}
    if not all(window.get(key) for key in ["start", "end", "timezone"]):
        blockers.append({"source": "release_window", "message": "start/end/timezone are required"})
    if data.get("risk_level") not in {"low", "medium", "high", "critical"}:
        blockers.append({"source": "risk_level", "message": "risk_level must be low/medium/high/critical"})
    return {"schema": "codex-release-change-validation-v1", "decision": "block" if blockers else "pass", "blockers": blockers}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate release change evidence")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_template = sub.add_parser("template")
    p_template.add_argument("--out", required=True)
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--file", required=True)
    p_validate.add_argument("--out")
    args = parser.parse_args()
    if args.cmd == "template":
        result = template()
        write_json(Path(args.out), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    result = validate(load_json(Path(args.file)))
    if args.out:
        write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
