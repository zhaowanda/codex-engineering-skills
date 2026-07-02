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


def load_project_understanding(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    base = path if path.is_dir() else path.parent
    if not base.exists():
        return {}
    result: dict[str, Any] = {}
    for name in ["repository_analysis", "api_surface", "config_surface", "dependency_surface", "code_index", "baseline", "baseline_quality"]:
        file = base / f"{name}.json"
        if file.exists():
            result[name] = load_json(file)
    return result


def project_context(project_understanding: dict[str, Any]) -> dict[str, Any]:
    repo = project_understanding.get("repository_analysis", {})
    api = project_understanding.get("api_surface", {})
    config = project_understanding.get("config_surface", {})
    deps = project_understanding.get("dependency_surface", {})
    index = project_understanding.get("code_index", {})
    baseline = project_understanding.get("baseline", {})
    project = str(repo.get("project") or api.get("project") or baseline.get("project") or "target-repo")
    repo_root = str(index.get("repo_root") or baseline.get("repo_root") or repo.get("repo_root") or "")
    entrypoints = [str(item) for item in as_list(repo.get("entrypoint_hints"))]
    modules = [str(item.get("module")) for item in as_list(baseline.get("module_hints")) if isinstance(item, dict) and item.get("module")]
    if not modules:
        modules = [str(item) for item in as_list(repo.get("top_level_directories"))]
    modules = [item for item in modules if item not in {".github", ".git", "tests", "__pycache__"}] or modules
    files = [str(item.get("path")) for item in as_list(index.get("files")) if isinstance(item, dict) and item.get("path")]
    routes = [item for item in as_list(api.get("routes")) if isinstance(item, dict)]
    config_items = [item for item in as_list(config.get("config_items")) if isinstance(item, dict)]
    test_hints = [str(item) for item in as_list(deps.get("test_command_hints"))] or [str(item) for item in as_list(repo.get("test_hints"))]
    return {
        "project": project,
        "repo_root": repo_root,
        "entrypoints": entrypoints,
        "modules": modules,
        "files": files,
        "routes": routes,
        "config_items": config_items,
        "test_hints": test_hints,
        "framework_hints": [str(item) for item in as_list(repo.get("framework_hints"))],
    }


def render(spec: dict[str, Any], project_understanding: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = project_context(project_understanding or {})
    doc_id = str(spec.get("doc_id") or "")
    title = str(spec.get("title") or "")
    requirements = [item for item in as_list(spec.get("requirements")) if isinstance(item, dict)]
    acceptance = [item for item in as_list(spec.get("acceptance_criteria")) if isinstance(item, dict)]
    summary = str(spec.get("requirement_summary") or title)
    actors = [str(item) for item in as_list(spec.get("actors"))] or ["user"]
    req_id = str(requirements[0].get("id") if requirements else "REQ-1")
    ac_id = str(acceptance[0].get("id") if acceptance else "AC-1")
    owner_module = ctx["modules"][0] if ctx["modules"] else "target module to be confirmed"
    read_first = ctx["entrypoints"] + ctx["files"][:5]
    owner_file = next((item for item in read_first if item.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs"))), owner_module)
    route_refs = [f"{item.get('method', '')} {item.get('route', '')} ({item.get('file', '')})".strip() for item in ctx["routes"][:5]]
    config_refs = [str(item.get("path")) for item in ctx["config_items"][:5]]
    test_evidence = [f"{cmd} evidence" for cmd in ctx["test_hints"][:3]] or ["test evidence"]
    return {
        "schema": "codex-technical-design-v1",
        "doc_id": doc_id,
        "title": title,
        "project_context": {
            "project": ctx["project"],
            "repo_root": ctx["repo_root"],
            "framework_hints": ctx["framework_hints"],
            "read_first": read_first,
            "test_command_hints": ctx["test_hints"],
        },
        "design_scope": spec.get("scope") or {"in_scope": [summary], "out_of_scope": [], "assumptions": [], "non_goals": []},
        "current_state_analysis": {
            "existing_behavior": f"{ctx['project']} currently handles the affected behavior through {', '.join(read_first[:3]) or owner_module}; implementation must verify this path before editing.",
            "code_entrypoints": read_first or [owner_module],
            "known_constraints": ["preserve existing contracts", "preserve existing permission and validation behavior"],
            "reuse_points": [owner_module, *(route_refs[:2] or [])],
        },
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
            "module": owner_file,
            "responsibility": summary,
            "input": "request data",
            "output": "updated behavior",
            "dependencies": route_refs + config_refs,
            "cohesion_reason": f"Keep requirement behavior in {ctx['project']} owner file/module.",
            "coupling_control": "Use existing contracts and avoid duplicating upstream business rules.",
        }],
        "logical_data_flow": [{"source": route_refs[0] if route_refs else "existing source", "transform": summary, "destination": owner_file, "owner": ctx["project"], "data_security": "classify during security review"}],
        "target_behavior": [{"requirement_id": str(item.get("id") or req_id), "behavior": str(item.get("summary") or summary)} for item in requirements] or [{"requirement_id": req_id, "behavior": summary}],
        "api_contracts": [{"contract": route_refs[0] if route_refs else "No API impact confirmed yet", "compatibility": "preserve existing consumers unless design updates contract", "old_consumer_impact": "review route consumers before implementation"}],
        "interface_examples": [{"name": route_refs[0] if route_refs else "no API request expected", "request": route_refs[0] if route_refs else "no API request expected", "response": f"response contract for {route_refs[0]}" if route_refs else "no API response change expected", "error_response": f"error contract for {route_refs[0]}" if route_refs else "no API error contract change expected"}],
        "compatibility_strategy": [{"old_consumer": "existing consumers", "old_data": "existing data", "rollback": "revert changed behavior", "behavior": "preserve backward compatibility"}],
        "compatibility_matrix": [{"consumer": "existing consumers", "old_behavior": "current behavior before this requirement", "new_behavior": summary, "compatibility": "backward compatible by default", "rollback_behavior": "revert changed behavior"}],
        "data_design": [{"read_rule": f"read through {owner_module}", "write_rule": f"write through {owner_module} only if requirement changes state", "migration": "none unless design update requires it"}],
        "permission_model": [{"role": actor, "rule": "preserve existing permission boundary", "negative_case": "unauthorized user cannot access changed behavior"} for actor in actors],
        "exception_and_edge_cases": [{"case": "missing/invalid input", "handling": "return validation error or preserve existing fallback"}],
        "non_functional_requirements": [{"type": "performance", "impact": "no extra heavy IO unless selected option requires it"}, {"type": "security", "impact": "no sensitive data exposure"}],
        "solution_options": [
            {"option_id": "T1", "name": "Minimal scoped change", "description": "Implement inside the current owner module using existing contracts.", "pros": ["low coupling", "small blast radius"], "cons": ["depends on existing boundaries"], "risk_level": "low", "validation": "unit/integration/browser evidence as applicable", "performance_impact": "minimal", "rollback_strategy": "revert scoped change"},
            {"option_id": "T2", "name": "New abstraction or contract", "description": "Introduce a new abstraction/API to isolate the behavior.", "pros": ["clear extension point"], "cons": ["larger change and migration risk"], "risk_level": "medium", "validation": "contract and regression tests", "performance_impact": "depends on implementation", "rollback_strategy": "revert contract and consumers"},
        ],
        "selected_solution": {"selected_option_id": "T1", "selection_reason": "Default to smallest safe change until code inspection proves abstraction is needed.", "decision_criteria": ["correctness", "low coupling", "rollback simplicity"], "tradeoffs": ["May need revision after architecture review"], "rejected_alternative_reasoning": [{"option_id": "T2", "reason": "Higher coordination and abstraction cost unless code inspection proves the extension point is required."}]},
        "design_traceability_matrix": [
            {
                "requirement_id": str(item.get("id") or req_id),
                "process_flow_refs": [title or summary],
                "module_refs": [owner_file],
                "data_flow_refs": [f"{route_refs[0] if route_refs else 'existing source'}->{owner_file}"],
                "api_contract_refs": route_refs or ["No API impact confirmed yet"],
                "ui_ue_refs": ["affected UI if any"],
                "test_refs": [f"TEST-{item.get('id') or req_id}"],
                "acceptance_refs": [str(ac.get("id") or ac_id) for ac in acceptance] or [ac_id],
                "selected_option_id": "T1",
                "decision_reason": "lowest initial risk",
            }
            for item in requirements
        ] or [{"requirement_id": req_id, "process_flow_refs": [title or summary], "module_refs": [owner_file], "data_flow_refs": [f"{route_refs[0] if route_refs else 'existing source'}->{owner_file}"], "api_contract_refs": route_refs or ["No API impact confirmed yet"], "ui_ue_refs": ["affected UI if any"], "test_refs": [f"TEST-{req_id}"], "acceptance_refs": [ac_id], "selected_option_id": "T1", "decision_reason": "lowest initial risk"}],
        "acceptance_mapping": [{"acceptance_id": str(item.get("id") or ac_id), "design_refs": [summary], "evidence_required": as_list(item.get("evidence_required")) or test_evidence} for item in acceptance] or [{"acceptance_id": ac_id, "design_refs": [summary], "evidence_required": test_evidence}],
        "ui_ue_design": [{"page_or_route": route_refs[0] if route_refs else "confirm if UI is affected", "user_goal": summary, "entry_point": "existing entry", "layout": "preserve existing layout unless requirement changes it", "interaction_flow": ["open affected behavior", "perform action", "verify result"], "states": ["loading", "success", "error"], "field_rules": ["preserve existing field validation and visibility"], "permission_visibility": "preserve role visibility", "acceptance_evidence": "browser evidence if UI changed"}],
        "test_strategy": [{"summary": f"Validate acceptance criteria for {summary}; detailed cases belong in test_design.json.", "evidence": test_evidence, "type": "strategy_summary", "test_design_ref": "test_design.json"}],
        "test_design_ref": "test_design.json",
        "open_questions": spec.get("open_questions", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render technical design from normalized spec")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--project-understanding")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = render(load_json(Path(args.spec)), load_project_understanding(Path(args.project_understanding)) if args.project_understanding else None)
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
