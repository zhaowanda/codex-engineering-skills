#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-uat-acceptance-v1"


def template() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "decision": "pending",
        "scope": [],
        "acceptors": [],
        "cases": [],
        "known_issues": [],
        "signoff": {"accepted": False, "by": "", "at": "", "notes": ""},
    }


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate(data: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    if data.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    if not data.get("scope"):
        blockers.append({"source": "scope", "message": "UAT scope is required"})
    if not data.get("acceptors"):
        blockers.append({"source": "acceptors", "message": "at least one acceptor is required"})
    cases = data.get("cases") if isinstance(data.get("cases"), list) else []
    if not cases:
        blockers.append({"source": "cases", "message": "UAT cases are required"})
    for idx, case in enumerate(cases):
        if isinstance(case, dict) and case.get("status") not in {"passed", "waived"}:
            blockers.append({"source": f"cases[{idx}]", "message": "UAT case is not passed or waived"})
    signoff = data.get("signoff") if isinstance(data.get("signoff"), dict) else {}
    if signoff.get("accepted") is not True or not signoff.get("by"):
        blockers.append({"source": "signoff", "message": "accepted signoff with owner is required"})
    unresolved = [item for item in data.get("known_issues", []) if isinstance(item, dict) and item.get("severity") in {"blocker", "high"} and item.get("status") != "accepted"]
    if unresolved:
        blockers.append({"source": "known_issues", "message": "blocking UAT issues remain", "count": len(unresolved)})
    return {"schema": "codex-uat-acceptance-validation-v1", "decision": "block" if blockers else "pass", "blockers": blockers}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate UAT acceptance evidence")
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
