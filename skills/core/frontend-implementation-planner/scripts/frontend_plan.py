#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-frontend-implementation-plan-v1"


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


def plan(ui: dict[str, Any], technical: dict[str, Any] | None = None) -> dict[str, Any]:
    technical = technical or {}
    if ui.get("decision") == "not_applicable" or ui.get("applicable") is False:
        return {"schema": SCHEMA, "decision": "not_applicable", "applicable": False, "blockers": [], "implementation_allowed": True}
    blockers: list[dict[str, str]] = []
    summary = ui.get("experience_summary") if isinstance(ui.get("experience_summary"), dict) else {}
    screens = [item for item in as_list(ui.get("screens")) if isinstance(item, dict)]
    route = str((screens[0].get("page_or_route") if screens else summary.get("entry_surface")) or "")
    read_first = as_list((technical.get("project_context") or {}).get("read_first")) if isinstance(technical.get("project_context"), dict) else []
    scope_model = technical.get("scope_model") if isinstance(technical.get("scope_model"), dict) else {}
    modify_files = [str(item) for item in as_list(scope_model.get("modify")) if str(item).strip()]
    reference_files = [str(item) for item in as_list(scope_model.get("reference_only")) if str(item).strip()]
    if not route or "confirm" in route.lower():
        blockers.append({"source": "route", "message": "Frontend route/page is not concrete."})
    if not read_first:
        blockers.append({"source": "project_context", "message": "No frontend source files were suggested; run project understanding/code index."})
    return {
        "schema": SCHEMA,
        "doc_id": ui.get("doc_id") or technical.get("doc_id"),
        "title": ui.get("title") or technical.get("title"),
        "decision": "block" if blockers else "pass",
        "applicable": True,
        "implementation_allowed": not blockers,
        "routes": [{"route": route, "entry_action": summary.get("trigger_action"), "user_goal": summary.get("user_goal")}],
        "candidate_files": (modify_files or [str(item) for item in read_first if str(item) not in reference_files])[:10],
        "reference_files": reference_files[:10],
        "component_work": [{"component_or_area": route or "affected component", "change": "implement UI/UE interaction flow and state matrix", "design_system_rule": "reuse existing controls before introducing new components"}],
        "state_handling": [item.get("state") for item in as_list(ui.get("state_matrix")) if isinstance(item, dict)],
        "api_dependencies": as_list((ui.get("frontend_contract") or {}).get("api_dependencies")) if isinstance(ui.get("frontend_contract"), dict) else [],
        "permission_handling": ["frontend controls visibility only", "backend/API authorization remains authoritative", "negative permission evidence required when roles are involved"],
        "test_and_evidence": as_list(ui.get("acceptance_evidence")) or ["browser acceptance evidence"],
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan frontend implementation from UI/UE design")
    parser.add_argument("--ui-ue-design", required=True)
    parser.add_argument("--technical-design")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = plan(load_json(Path(args.ui_ue_design)), load_json(Path(args.technical_design)) if args.technical_design else {})
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") in {"pass", "not_applicable"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
