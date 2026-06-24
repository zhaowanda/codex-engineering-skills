#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


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


def render(spec: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(spec.get("doc_id") or "")
    title = str(spec.get("title") or "")
    requirements = [item for item in as_list(spec.get("requirements")) if isinstance(item, dict)]
    acceptance = [item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]
    summary = str(spec.get("requirement_summary") or title)
    actors = [str(item) for item in as_list(spec.get("actors"))] or ["user"]
    req_id = str(requirements[0].get("id") if requirements else "REQ-1")
    ac_id = str(acceptance[0].get("id") if acceptance else "AC-1")
    return {
        "schema": "codex-technical-design-v1",
        "doc_id": doc_id,
        "title": title,
        "design_scope": spec.get("scope") or {"in_scope": [summary], "out_of_scope": [], "assumptions": [], "non_goals": []},
        "requirement_trace": [{"requirement_id": str(item.get("id")), "summary": str(item.get("summary"))} for item in requirements],
        "business_rule_mapping": [
            {"requirement_id": req_id, "technical_enforcement": str(rule.get("rule")), "source_of_truth": "spec.business_rules"}
            for rule in as_list(spec.get("business_rules")) if isinstance(rule, dict)
        ] or [{"requirement_id": req_id, "technical_enforcement": "Implement behavior described by normalized spec.", "source_of_truth": "spec.requirements"}],
        "process_flow": [{
            "flow_name": title or summary,
            "actors": actors,
            "steps": [{"step": 1, "actor": actors[0], "action": summary, "input": "user request/context", "output": "expected behavior", "exception": "show existing error handling or validation failure"}],
            "success_end_state": "Acceptance criteria pass.",
            "failure_end_states": ["Validation failure", "Dependency unavailable"],
        }],
        "module_decomposition": [{
            "module": "target module to be confirmed",
            "responsibility": summary,
            "input": "request data",
            "output": "updated behavior",
            "dependencies": [],
            "cohesion_reason": "Keep requirement behavior in one owner module.",
            "coupling_control": "Use existing contracts and avoid duplicating upstream business rules.",
        }],
        "logical_data_flow": [{"source": "existing source", "transform": summary, "destination": "affected UI/API/storage", "owner": "owning module", "data_security": "classify during security review"}],
        "target_behavior": [{"requirement_id": req_id, "behavior": summary}],
        "api_contracts": [{"contract": "No API impact confirmed yet", "compatibility": "must be confirmed before implementation", "old_consumer_impact": "unknown until code inspection"}],
        "compatibility_strategy": [{"old_consumer": "existing consumers", "old_data": "existing data", "rollback": "revert changed behavior", "behavior": "preserve backward compatibility"}],
        "data_design": [{"read_rule": "confirm during code inspection", "write_rule": "confirm during code inspection", "migration": "none unless design update requires it"}],
        "permission_model": [{"role": actor, "rule": "preserve existing permission boundary", "negative_case": "unauthorized user cannot access changed behavior"} for actor in actors],
        "exception_and_edge_cases": [{"case": "missing/invalid input", "handling": "return validation error or preserve existing fallback"}],
        "non_functional_requirements": [{"type": "performance", "impact": "no extra heavy IO unless selected option requires it"}, {"type": "security", "impact": "no sensitive data exposure"}],
        "solution_options": [
            {"option_id": "T1", "name": "Minimal scoped change", "description": "Implement inside the current owner module using existing contracts.", "pros": ["low coupling", "small blast radius"], "cons": ["depends on existing boundaries"], "risk_level": "low", "validation": "unit/integration/browser evidence as applicable", "performance_impact": "minimal", "rollback_strategy": "revert scoped change"},
            {"option_id": "T2", "name": "New abstraction or contract", "description": "Introduce a new abstraction/API to isolate the behavior.", "pros": ["clear extension point"], "cons": ["larger change and migration risk"], "risk_level": "medium", "validation": "contract and regression tests", "performance_impact": "depends on implementation", "rollback_strategy": "revert contract and consumers"},
        ],
        "selected_solution": {"selected_option_id": "T1", "selection_reason": "Default to smallest safe change until code inspection proves abstraction is needed.", "decision_criteria": ["correctness", "low coupling", "rollback simplicity"], "tradeoffs": ["May need revision after architecture review"]},
        "design_traceability_matrix": [{"requirement_id": req_id, "process_flow_refs": [title or summary], "module_refs": ["target module to be confirmed"], "data_flow_refs": ["existing source->affected target"], "api_contract_refs": ["No API impact confirmed yet"], "ui_ue_refs": ["affected UI if any"], "test_refs": [f"TEST-{req_id}"], "acceptance_refs": [ac_id], "selected_option_id": "T1", "decision_reason": "lowest initial risk"}],
        "acceptance_mapping": [{"acceptance_id": str(item.get("id") or ac_id), "design_refs": [summary], "evidence_required": as_list(item.get("evidence_required")) or ["test evidence"]} for item in acceptance] or [{"acceptance_id": ac_id, "design_refs": [summary], "evidence_required": ["test evidence"]}],
        "ui_ue_design": [{"page_or_route": "confirm if UI is affected", "user_goal": summary, "entry_point": "existing entry", "layout": "preserve existing layout unless requirement changes it", "interaction_flow": ["open affected behavior", "perform action", "verify result"], "states": ["loading", "success", "error"], "field_rules": [], "permission_visibility": "preserve role visibility", "acceptance_evidence": "browser evidence if UI changed"}],
        "test_strategy": [{"case": summary, "evidence": ["automated or manual execution evidence"], "type": "functional"}],
        "open_questions": spec.get("open_questions", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render technical design from normalized spec")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = render(load_json(Path(args.spec)))
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
