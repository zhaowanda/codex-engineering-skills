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
    index = project_understanding.get("code_index", {})
    baseline = project_understanding.get("baseline", {})
    api = project_understanding.get("api_surface", {})
    deps = project_understanding.get("dependency_surface", {})
    project = str(repo.get("project") or baseline.get("project") or api.get("project") or "target-repo")
    repo_path = str(index.get("repo_root") or baseline.get("repo_root") or repo.get("repo_root") or "")
    modules = [str(item.get("module")) for item in as_list(baseline.get("module_hints")) if isinstance(item, dict) and item.get("module")]
    if not modules:
        modules = [str(item) for item in as_list(repo.get("top_level_directories"))]
    modules = [item for item in modules if item not in {".github", ".git", "tests", "__pycache__"}] or modules
    routes = [item for item in as_list(api.get("routes")) if isinstance(item, dict)]
    tests = [str(item) for item in as_list(deps.get("test_command_hints"))] or [str(item) for item in as_list(repo.get("test_hints"))]
    return {"project": project, "repo_path": repo_path, "modules": modules, "routes": routes, "tests": tests}


def render(spec: dict[str, Any], technical: dict[str, Any], project_understanding: dict[str, Any] | None = None) -> dict[str, Any]:
    ctx = project_context(project_understanding or {})
    doc_id = str(spec.get("doc_id") or technical.get("doc_id") or "")
    title = str(spec.get("title") or technical.get("title") or "")
    summary = str(spec.get("requirement_summary") or title)
    reqs = [item for item in as_list(spec.get("requirements")) if isinstance(item, dict)]
    req_id = str(reqs[0].get("id") if reqs else "REQ-1")
    owner_repo = ctx["project"]
    repo_path = ctx["repo_path"]
    tech_modules = [
        str(item.get("module"))
        for item in as_list(technical.get("module_decomposition"))
        if isinstance(item, dict) and item.get("module")
    ]
    owner_module = tech_modules[0] if tech_modules else (ctx["modules"][0] if ctx["modules"] else "target module to be confirmed")
    route_contract = ""
    producer = owner_repo
    if ctx["routes"]:
        route = ctx["routes"][0]
        route_contract = f"{route.get('method', '')} {route.get('route', '')} ({route.get('file', '')})".strip()
        producer = str(route.get("file") or owner_repo)
    return {
        "schema": "codex-architecture-design-v1",
        "doc_id": doc_id,
        "title": title,
        "architecture_scope": {"in_scope": as_list((spec.get("scope") or {}).get("in_scope")) or [summary], "out_of_scope": as_list((spec.get("scope") or {}).get("out_of_scope")), "assumptions": as_list((spec.get("scope") or {}).get("assumptions")), "decision_drivers": ["low coupling", "clear ownership", "rollback safety"]},
        "current_architecture": {
            "system_context": f"{owner_repo} owns the initial change boundary for this requirement and must preserve existing upstream/downstream contracts.",
            "repo_entrypoints": [owner_module, route_contract or "existing entrypoint to be confirmed"],
            "upstream_downstream": [f"{route_contract or 'existing producer'} -> {owner_repo}"],
            "constraints": ["keep owner boundary narrow", "preserve backward compatibility", "support rollback by reverting owner repo"],
        },
        "architecture_options": [
            {"option_id": "A1", "name": "Single owner repository change", "description": "Implement in the current owner repo and preserve external contracts.", "owner_repos": [owner_repo], "confirm_only_repos": [producer] if producer != owner_repo else [], "pros": ["small blast radius", "simple rollback"], "cons": ["requires owner confirmation"], "risk_level": "low", "validation": "repo tests and acceptance evidence", "performance_impact": "minimal", "rollback_strategy": f"revert {owner_repo}"},
            {"option_id": "A2", "name": "Cross-repository contract change", "description": "Change producer and consumer contracts across repositories.", "owner_repos": ["producer-repo", "consumer-repo"], "confirm_only_repos": [owner_repo], "pros": ["explicit contract"], "cons": ["coordination and compatibility risk"], "risk_level": "medium", "validation": "contract, integration, and regression tests", "performance_impact": "depends on new calls", "rollback_strategy": "ordered rollback consumer then producer"},
        ],
        "selected_architecture": {"selected_option_id": "A1", "selection_reason": "Default to smallest owner-boundary change until code inspection requires cross-repo work.", "decision_criteria": ["ownership", "compatibility", "rollback"], "tradeoffs": ["May be revised after repo routing"], "rejected_alternative_reasoning": [{"option_id": "A2", "reason": "Cross-repository contract work adds compatibility and release-order risk unless the existing owner boundary cannot satisfy the requirement."}]},
        "architecture_traceability_matrix": [
            {"requirement_id": str(item.get("id") or req_id), "component_boundary_refs": [f"{owner_repo} owns change"], "module_topology_refs": [owner_module], "data_flow_refs": [f"{route_contract or 'existing source'}->{owner_repo}"], "integration_sequence_refs": ["load/execute affected behavior"], "contract_refs": [route_contract or "preserve existing contracts"], "selected_architecture_option_id": "A1", "decision_reason": "lowest coordination risk"}
            for item in reqs
        ] or [{"requirement_id": req_id, "component_boundary_refs": [f"{owner_repo} owns change"], "module_topology_refs": [owner_module], "data_flow_refs": [f"{route_contract or 'existing source'}->{owner_repo}"], "integration_sequence_refs": ["load/execute affected behavior"], "contract_refs": [route_contract or "preserve existing contracts"], "selected_architecture_option_id": "A1", "decision_reason": "lowest coordination risk"}],
        "component_boundaries": [{"component": owner_repo, "role": "owner", "exclusion": "do not move unrelated responsibilities"}],
        "module_topology": [{"repo": owner_repo, "module": owner_module, "responsibility": summary, "depends_on": ["existing API/config dependencies"], "boundary_rule": "keep change inside owner module", "change_type": "modify"}],
        "repo_responsibilities": [{"repo": owner_repo, "repo_path": repo_path, "role": "modify", "responsibility": summary}],
        "cross_repo_contracts": [{"producer": producer, "consumer": owner_repo, "contract": route_contract or f"{owner_repo} internal contract", "compatibility": "backward compatible", "failure_mode": "fallback/error state"}],
        "cross_repo_dependency_graph": [{"from": producer, "to": owner_repo, "contract": route_contract or f"{owner_repo} internal contract", "change": "confirm only unless implementation proves contract change is required"}],
        "data_flow": [{"source": route_contract or "existing source", "target": owner_repo, "rule": "read/write only through owner boundary"}],
        "data_ownership": [{"business_object": summary or title or doc_id, "owner_repo": owner_repo, "write_authority": owner_module, "consistency_rule": "preserve existing consistency"}],
        "integration_sequence": [{"step": 1, "actor": owner_repo, "action": summary, "failure_handling": "preserve existing failure behavior"}],
        "failure_isolation": [{"failure": "upstream dependency unavailable or returns old shape", "isolation": "preserve existing fallback/error behavior", "user_impact": "no broader repository failure"}],
        "security_and_permission": [{"control": "preserve existing auth/data-scope checks", "impact": "review before implementation"}],
        "observability": [{"signal": "error logs and business success metric", "owner": owner_repo}],
        "monitoring_alerts": [{"signal": "error rate or failed acceptance path", "owner": owner_repo, "trigger": "increase after release", "action": "rollback or hotfix"}],
        "deployment_topology": [{"repo": owner_repo, "artifact": "existing deploy artifact", "environment": "standard promotion"}],
        "deployment_impact": [{"order": f"{owner_repo} first", "config": "none unless configuration design adds it"}],
        "deployment_impact_matrix": [{"repo": owner_repo, "artifact": "existing deploy artifact", "order": 1, "config_change": "none unless configuration design adds it", "restart_required": "standard deployment restart only"}],
        "migration_strategy": [{"migration_type": "none by default", "forward_action": "deploy changed repo", "backward_compatibility": "preserve existing contracts", "rollback_action": "revert changed repo"}],
        "gray_release_strategy": [{"strategy": "standard rollout", "fallback": "rollback"}],
        "rollback_strategy": [{"repo": owner_repo, "steps": ["revert commit", "redeploy previous artifact"], "data_risk": "none unless data design changes"}],
        "decision_records": [{"decision": "start with owner-repo scoped architecture", "alternatives": ["cross-repo contract change"], "reason": "minimize coupling and release risk"}],
        "architecture_risks": [] if repo_path else [{"risk": "owner repo not yet routed", "mitigation": "fill repo_path and rerun delivery plan before git/edit"}],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render architecture design from spec and technical design")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--technical-design", required=True)
    parser.add_argument("--project-understanding")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = render(load_json(Path(args.spec)), load_json(Path(args.technical_design)), load_project_understanding(Path(args.project_understanding)) if args.project_understanding else None)
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
