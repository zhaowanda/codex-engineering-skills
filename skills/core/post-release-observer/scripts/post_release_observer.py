#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


SCHEMA = "codex-post-release-observation-v1"


def template() -> dict:
    return {
        "schema": SCHEMA,
        "decision": "pending",
        "observation_window": {"start": "", "end": "", "duration_minutes": 0},
        "metrics": [],
        "logs_checked": [],
        "alerts_checked": [],
        "business_checks": [],
        "incidents": [],
        "close": False,
        "closed_by": "",
    }


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate(data: dict, regulated: bool = False) -> dict:
    blockers = []
    if data.get("schema") != SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {SCHEMA}"})
    window = data.get("observation_window") if isinstance(data.get("observation_window"), dict) else {}
    if not window.get("duration_minutes"):
        blockers.append({"source": "observation_window", "message": "duration_minutes is required"})
    if not data.get("metrics") and not data.get("logs_checked") and not data.get("business_checks"):
        blockers.append({"source": "evidence", "message": "metrics, logs, or business checks are required"})
    incidents = data.get("incidents")
    unresolved_incidents = [
        item for item in data.get("incidents", [])
        if not isinstance(item, dict) or item.get("status") not in {"resolved", "closed"}
    ] if isinstance(incidents, list) else [incidents] if incidents else []
    if unresolved_incidents:
        blockers.append({"source": "incidents", "message": "incidents must be resolved before close"})
    if data.get("close") is not True or not data.get("closed_by"):
        blockers.append({"source": "close", "message": "close=true and closed_by are required"})
    if regulated:
        if not window.get("start") or not window.get("end"):
            blockers.append({"source": "observation_window", "message": "regulated observation requires start and end"})
        evidence_groups = {
            "metrics": data.get("metrics"),
            "logs_checked": data.get("logs_checked"),
            "alerts_checked": data.get("alerts_checked"),
            "business_checks": data.get("business_checks"),
        }
        for group, items in evidence_groups.items():
            if not isinstance(items, list) or not items:
                blockers.append({"source": group, "message": f"regulated observation requires {group}"})
                continue
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    blockers.append({"source": group, "message": f"{group}[{index}] must be structured evidence"})
                    continue
                for field in ["provider", "evidence_id", "observed_at", "status"]:
                    if not item.get(field):
                        blockers.append({"source": group, "message": f"{group}[{index}].{field} is required"})
                if item.get("status") not in {"healthy", "pass", "resolved"}:
                    blockers.append({"source": group, "message": f"{group}[{index}] is not healthy"})
        if not data.get("closed_at") or not data.get("close_evidence_id"):
            blockers.append({"source": "close", "message": "regulated observation requires closed_at and close_evidence_id"})
    return {"schema": "codex-post-release-observation-validation-v1", "decision": "block" if blockers else "pass", "blockers": blockers}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or validate post-release observation")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_template = sub.add_parser("template")
    p_template.add_argument("--out", required=True)
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--file", required=True)
    p_validate.add_argument("--out")
    p_validate.add_argument("--regulated", action="store_true")
    args = parser.parse_args()
    if args.cmd == "template":
        result = template()
        write_json(Path(args.out), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    result = validate(load_json(Path(args.file)), regulated=args.regulated)
    if args.out:
        write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
