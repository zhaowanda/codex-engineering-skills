#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-ui-ue-design-v1"
UI_TERMS = ("ui", "ux", "frontend", "page", "route", "button", "menu", "form", "table", "dashboard", "页面", "按钮", "菜单", "表单", "表格", "筛选", "弹窗", "前端", "展示")


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


def blob(*values: Any) -> str:
    return json.dumps(values, ensure_ascii=False).lower()


def has_ui_signal(spec: dict[str, Any], technical: dict[str, Any]) -> bool:
    impacts = {str(item.get("area") or "").lower() for item in as_list(spec.get("impact_surface")) if isinstance(item, dict)}
    return bool({"ui", "frontend"} & impacts) or any(term in blob(spec, technical.get("ui_ue_design"), technical.get("target_behavior")) for term in UI_TERMS)


def first_text(*values: Any, default: str = "") -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, list) and value:
            first = first_text(*value)
            if first:
                return first
        if isinstance(value, dict):
            first = first_text(*value.values())
            if first:
                return first
    return default


def source_entry_text(spec: dict[str, Any]) -> str:
    candidates: list[str] = []
    for item in as_list(spec.get("source_trace")):
        if isinstance(item, dict):
            value = str(item.get("text") or item.get("line") or item.get("content") or "")
        else:
            value = str(item or "")
        if any(prefix in value for prefix in ["入口", "entry", "Entry"]):
            candidates.append(value.split(":", 1)[-1].split("：", 1)[-1].strip())
    for item in as_list(spec.get("entrypoints")):
        if isinstance(item, dict):
            candidates.append(first_text(item.get("name"), item.get("entry"), item.get("trigger"), item.get("action")))
        else:
            candidates.append(str(item))
    return next((item for item in candidates if item), "")


def page_from_entry(entry: str, summary: str) -> str:
    text = entry or summary
    for marker in ["页面", "页", "page", "route"]:
        if marker in text:
            return text
    return text or "affected page or route must be confirmed"


def existing_ui_rows(technical: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in as_list(technical.get("ui_ue_design")) if isinstance(item, dict)]


def design(spec: dict[str, Any], technical: dict[str, Any] | None = None) -> dict[str, Any]:
    technical = technical or {}
    doc_id = str(spec.get("doc_id") or technical.get("doc_id") or "")
    title = str(spec.get("title") or technical.get("title") or "UI/UE design")
    summary = str(spec.get("requirement_summary") or title)
    ui_rows = existing_ui_rows(technical)
    applicable = has_ui_signal(spec, technical)
    blockers: list[dict[str, str]] = []
    if not applicable:
        return {
            "schema": SCHEMA,
            "doc_id": doc_id,
            "title": title,
            "decision": "not_applicable",
            "applicable": False,
            "reason": "No frontend, page, route, menu, button, table, form, or user-visible interaction signal was detected.",
            "blockers": [],
            "warnings": [],
        }

    source = ui_rows[0] if ui_rows else {}
    spec_entry = source_entry_text(spec)
    raw_page = first_text(source.get("page_or_route"), default="")
    raw_entry = first_text(source.get("entry_point"), default="")
    page = spec_entry if "confirm" in raw_page.lower() or not raw_page else raw_page
    page = page_from_entry(page, summary)
    entry = spec_entry if raw_entry in {"", "existing entry"} or "confirm" in raw_entry.lower() else raw_entry
    if "confirm" in page.lower() or "must be confirmed" in page.lower():
        blockers.append({"source": "page_or_route", "message": "UI route/page is not concrete enough for implementation."})
    if entry in {"existing entry", ""} or "must be confirmed" in entry.lower():
        blockers.append({"source": "entry_point", "message": "User entry action must name the menu, button, tab, form submit, table action, or route load."})

    state_matrix = [
        {"state": "loading", "user_feedback": "show bounded loading indicator", "system_rule": "disable duplicate submit or action while request is pending", "evidence": "screenshot or component assertion"},
        {"state": "empty", "user_feedback": "show domain-specific empty state without hiding available actions", "system_rule": "empty data must not be treated as an error", "evidence": "empty-data browser evidence"},
        {"state": "success", "user_feedback": "show updated result and success feedback where the workflow changes state", "system_rule": "result reflects backend/source-of-truth response", "evidence": "happy-path browser evidence"},
        {"state": "validation_error", "user_feedback": "show field-level or action-level validation message", "system_rule": "client validation cannot replace server validation", "evidence": "negative validation evidence"},
        {"state": "permission_denied", "user_feedback": "hide or disable unauthorized entry and show server denial when directly requested", "system_rule": "server remains the authority", "evidence": "permission negative evidence"},
        {"state": "dependency_error", "user_feedback": "show retryable error or fallback defined by product flow", "system_rule": "do not lose user input", "evidence": "network/API failure evidence"},
    ]
    api_refs = []
    for item in as_list(technical.get("api_contracts")):
        if isinstance(item, dict):
            api_refs.append(str(item.get("contract") or item.get("api") or ""))
    result = {
        "schema": SCHEMA,
        "doc_id": doc_id,
        "title": title,
        "decision": "block" if blockers else "pass",
        "applicable": True,
        "experience_summary": {
            "user_goal": first_text(source.get("user_goal"), summary),
            "entry_surface": page,
            "trigger_action": entry,
            "business_outcome": summary,
            "primary_personas": as_list(spec.get("personas")) or as_list(spec.get("actors")) or ["user"],
        },
        "screens": [{
            "page_or_route": page,
            "information_architecture": ["primary task area", "filters/actions if applicable", "result/status area", "feedback/error area"],
            "layout_zones": as_list(source.get("layout")) or ["reuse existing layout"],
            "component_mapping": ["map to existing design-system controls before introducing new components"],
            "responsive_rules": ["preserve task completion on desktop and mobile widths", "avoid text overlap and horizontal overflow"],
        }],
        "interaction_flows": [{
            "name": "primary user flow",
            "steps": as_list(source.get("interaction_flow")) or ["open entry", "perform action", "system validates", "result is visible"],
            "exception_paths": ["validation error", "permission denied", "dependency error", "empty result"],
        }],
        "state_matrix": state_matrix,
        "content_i18n": {"microcopy": ["success, error, empty, validation, and confirmation copy must use product language"], "i18n_rule": "new visible text must follow repository i18n conventions when present"},
        "accessibility": ["keyboard reachable entry/action", "visible focus state", "semantic labels for icon-only actions", "color is not the only status signal"],
        "frontend_contract": {"api_dependencies": [item for item in api_refs if item], "data_fields": as_list(spec.get("data_fields")), "permission_dependencies": as_list(technical.get("permission_model"))},
        "acceptance_evidence": ["browser happy path", "empty/error state evidence", "permission negative evidence when roles are involved", "screenshot or visual regression for layout-sensitive changes"],
        "blockers": blockers,
        "warnings": [] if not blockers else [{"source": "ui_ue_design", "message": "Resolve UI entrypoint ambiguity before implementation."}],
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate UI/UE design artifact")
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
