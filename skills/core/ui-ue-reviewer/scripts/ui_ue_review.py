#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-ui-ue-review-v1"
REQUIRED_STATES = {"loading", "empty", "success", "validation_error", "permission_denied", "dependency_error"}


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


def finding(area: str, severity: str, message: str, evidence: Any, suggestion: str) -> dict[str, Any]:
    return {"area": area, "severity": severity, "message": message, "evidence": evidence, "suggestion": suggestion}


def score(findings: list[dict[str, Any]]) -> dict[str, Any]:
    weights = {"blocker": 35, "high": 15, "medium": 6, "low": 2}
    penalty = sum(weights.get(str(item.get("severity")), 0) for item in findings)
    value = max(0, 100 - penalty)
    level = "block" if any(item.get("severity") == "blocker" for item in findings) else "needs_revision" if value < 85 else "expert_ready" if value >= 90 else "reviewable"
    return {"score": value, "level": level}


def review(design: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    if design.get("decision") == "not_applicable" or design.get("applicable") is False:
        return {"schema": SCHEMA, "decision": "not_applicable", "score": 100, "level": "not_applicable", "findings": [], "blockers": [], "readiness_gate": {"frontend_implementation_allowed": True}}
    if design.get("decision") == "block":
        findings.append(finding("ui_ue_entrypoint", "blocker", "UI/UE design is blocked", design.get("blockers"), "Clarify blocked UI/UE inputs before implementation."))
    summary = design.get("experience_summary") if isinstance(design.get("experience_summary"), dict) else {}
    if not summary.get("user_goal") or not summary.get("business_outcome"):
        findings.append(finding("ui_ue_goal", "high", "UI/UE design lacks user goal or business outcome", summary, "State the user's task and the business outcome."))
    entry = str(summary.get("trigger_action") or "")
    if not entry or entry == "existing entry" or "confirm" in entry.lower():
        findings.append(finding("ui_ue_entrypoint", "high", "UI entry action is not concrete", entry, "Name the menu, button, tab, table action, form submit, route load, or refresh trigger."))
    if not as_list(design.get("screens")):
        findings.append(finding("ui_ue_information_architecture", "high", "screens are missing", "screens empty", "Define page/route, information architecture, layout zones, and component mapping."))
    if not as_list(design.get("interaction_flows")):
        findings.append(finding("ui_ue_interaction", "high", "interaction flows are missing", "interaction_flows empty", "Define ordered user actions, system responses, and exception paths."))
    states = {str(item.get("state")) for item in as_list(design.get("state_matrix")) if isinstance(item, dict)}
    missing_states = sorted(REQUIRED_STATES - states)
    if missing_states:
        findings.append(finding("ui_ue_states", "high", "state matrix is incomplete", {"missing": missing_states}, "Cover loading, empty, success, validation error, permission denied, and dependency error states."))
    contract = design.get("frontend_contract") if isinstance(design.get("frontend_contract"), dict) else {}
    if not contract:
        findings.append(finding("ui_ue_contract", "medium", "frontend contract dependencies are missing", "frontend_contract empty", "List API, data, and permission dependencies needed by the UI."))
    evidence = as_list(design.get("acceptance_evidence"))
    if len(evidence) < 2:
        findings.append(finding("ui_ue_evidence", "high", "UI/UE acceptance evidence is too thin", evidence, "Require browser/component/screenshot/accessibility evidence for the interaction."))
    scored = score(findings)
    return {
        "schema": SCHEMA,
        "decision": "pass" if scored["level"] in {"expert_ready", "reviewable"} else "block",
        "score": scored["score"],
        "level": scored["level"],
        "findings": findings,
        "blockers": [item for item in findings if item.get("severity") in {"blocker", "high"}],
        "readiness_gate": {"frontend_implementation_allowed": scored["level"] in {"expert_ready", "reviewable"}},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Review UI/UE design artifact")
    parser.add_argument("--ui-ue-design", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = review(load_json(Path(args.ui_ue_design)))
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") in {"pass", "not_applicable"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
