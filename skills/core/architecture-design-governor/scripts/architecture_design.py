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


def render(spec: dict[str, Any], technical: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(spec.get("doc_id") or technical.get("doc_id") or "")
    title = str(spec.get("title") or technical.get("title") or "")
    summary = str(spec.get("requirement_summary") or title)
    reqs = [item for item in as_list(spec.get("requirements")) if isinstance(item, dict)]
    req_id = str(reqs[0].get("id") if reqs else "REQ-1")
    return {
        "schema": "codex-architecture-design-v1",
        "doc_id": doc_id,
        "title": title,
        "architecture_scope": {"in_scope": as_list((spec.get("scope") or {}).get("in_scope")) or [summary], "out_of_scope": as_list((spec.get("scope") or {}).get("out_of_scope")), "assumptions": as_list((spec.get("scope") or {}).get("assumptions")), "decision_drivers": ["low coupling", "clear ownership", "rollback safety"]},
        "architecture_options": [
            {"option_id": "A1", "name": "Single owner repository change", "description": "Implement in the current owner repo and preserve external contracts.", "owner_repos": ["target-repo"], "confirm_only_repos": [], "pros": ["small blast radius", "simple rollback"], "cons": ["requires owner confirmation"], "risk_level": "low", "validation": "repo tests and acceptance evidence", "performance_impact": "minimal", "rollback_strategy": "revert target repo"},
            {"option_id": "A2", "name": "Cross-repository contract change", "description": "Change producer and consumer contracts across repositories.", "owner_repos": ["producer-repo", "consumer-repo"], "confirm_only_repos": [], "pros": ["explicit contract"], "cons": ["coordination and compatibility risk"], "risk_level": "medium", "validation": "contract, integration, and regression tests", "performance_impact": "depends on new calls", "rollback_strategy": "ordered rollback consumer then producer"},
        ],
        "selected_architecture": {"selected_option_id": "A1", "selection_reason": "Default to smallest owner-boundary change until code inspection requires cross-repo work.", "decision_criteria": ["ownership", "compatibility", "rollback"], "tradeoffs": ["May be revised after repo routing"]},
        "architecture_traceability_matrix": [{"requirement_id": req_id, "component_boundary_refs": ["target-repo owns change"], "module_topology_refs": ["target module to be confirmed"], "data_flow_refs": ["existing source->affected target"], "integration_sequence_refs": ["load/execute affected behavior"], "contract_refs": ["preserve existing contracts"], "selected_architecture_option_id": "A1", "decision_reason": "lowest coordination risk"}],
        "component_boundaries": [{"component": "target-repo", "role": "owner", "exclusion": "do not move unrelated responsibilities"}],
        "module_topology": [{"repo": "target-repo", "module": "target module to be confirmed", "responsibility": summary, "depends_on": [], "boundary_rule": "keep change inside owner module", "change_type": "modify"}],
        "repo_responsibilities": [{"repo": "target-repo", "repo_path": "", "role": "modify", "responsibility": summary}],
        "cross_repo_contracts": [{"producer": "existing producer", "consumer": "target-repo", "contract": "preserve existing contract unless design updates it", "compatibility": "backward compatible", "failure_mode": "fallback/error state"}],
        "data_flow": [{"source": "existing source", "target": "target-repo", "rule": "read/write only through owner boundary"}],
        "data_ownership": [{"business_object": "affected object", "owner_repo": "target-repo", "write_authority": "owner module", "consistency_rule": "preserve existing consistency"}],
        "integration_sequence": [{"step": 1, "actor": "target-repo", "action": summary, "failure_handling": "preserve existing failure behavior"}],
        "security_and_permission": [{"control": "preserve existing auth/data-scope checks", "impact": "review before implementation"}],
        "observability": [{"signal": "error logs and business success metric", "owner": "target owner"}],
        "monitoring_alerts": [{"signal": "error rate or failed acceptance path", "owner": "target owner", "trigger": "increase after release", "action": "rollback or hotfix"}],
        "deployment_topology": [{"repo": "target-repo", "artifact": "existing deploy artifact", "environment": "standard promotion"}],
        "deployment_impact": [{"order": "target-repo first", "config": "none unless configuration design adds it"}],
        "migration_strategy": [{"migration_type": "none by default", "forward_action": "deploy changed repo", "backward_compatibility": "preserve existing contracts", "rollback_action": "revert changed repo"}],
        "gray_release_strategy": [{"strategy": "standard rollout", "fallback": "rollback"}],
        "rollback_strategy": [{"repo": "target-repo", "steps": ["revert commit", "redeploy previous artifact"], "data_risk": "none unless data design changes"}],
        "decision_records": [{"decision": "start with owner-repo scoped architecture", "alternatives": ["cross-repo contract change"], "reason": "minimize coupling and release risk"}],
        "architecture_risks": [{"risk": "owner repo not yet routed", "mitigation": "fill repo_path and rerun delivery plan before git/edit"}],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Render architecture design from spec and technical design")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--technical-design", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = render(load_json(Path(args.spec)), load_json(Path(args.technical_design)))
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
