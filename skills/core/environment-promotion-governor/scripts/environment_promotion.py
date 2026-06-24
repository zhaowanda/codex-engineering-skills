#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-environment-promotion-v1"
ENVS = ["dev", "sit", "uat", "pre", "prod"]


def template() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "decision": "pending",
        "environments": [
            {
                "name": env,
                "entry_criteria": [],
                "exit_criteria": [],
                "configuration_differences": [],
                "validation_evidence": [],
                "rollback_ready": False,
                "approver": "",
                "status": "pending",
            }
            for env in ENVS
        ],
        "blockers": [],
    }


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate(data: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    if data.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    envs = data.get("environments") if isinstance(data.get("environments"), list) else []
    by_name = {item.get("name"): item for item in envs if isinstance(item, dict)}
    for env in ENVS:
        item = by_name.get(env)
        if not item:
            blockers.append({"source": env, "message": "environment entry missing"})
            continue
        for key in ["entry_criteria", "exit_criteria", "validation_evidence"]:
            if not item.get(key):
                blockers.append({"source": env, "message": f"{key} is required"})
        if env in {"pre", "prod"} and not item.get("approver"):
            blockers.append({"source": env, "message": "approver is required for pre/prod"})
        if env == "prod" and not item.get("rollback_ready"):
            blockers.append({"source": env, "message": "rollback_ready is required for prod"})
        if item.get("status") in {"blocked", "failed"}:
            blockers.append({"source": env, "message": f"environment status is {item.get('status')}"})
    return {
        "schema": "codex-environment-promotion-validation-v1",
        "decision": "block" if blockers else "pass",
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate environment promotion evidence")
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
