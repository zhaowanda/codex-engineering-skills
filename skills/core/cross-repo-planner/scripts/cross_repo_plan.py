#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
from typing import Any


GRAPH_SCHEMA = "codex-cross-repo-execution-graph-v1"
READINESS_SCHEMA = "codex-cross-repo-readiness-v1"
RELEASE_SCHEMA = "codex-cross-repo-release-plan-v1"
VALIDATION_SCHEMA = "codex-cross-repo-graph-validation-v1"
CONTRACT_TERMS = {"api", "route", "contract", "dto", "event", "schema", "feign", "mq", "database", "db", "config", "permission", "dependency"}
SERIAL_TERMS = {"database", "db", "migration", "config", "permission", "dependency", "release"}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_yaml_like(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_registry(path: Path | None) -> dict[str, dict[str, Any]]:
    if not path:
        return {}
    raw = read_json(path) if path.suffix == ".json" else load_yaml_like(path)
    projects = raw.get("projects", []) if isinstance(raw.get("projects"), list) else []
    result: dict[str, dict[str, Any]] = {}
    for item in projects:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        name = str(item["name"])
        deps = item.get("dependencies") if isinstance(item.get("dependencies"), list) else item.get("relatedProjects")
        analysis = item.get("analysis") if isinstance(item.get("analysis"), dict) else {}
        result[name] = {
            "name": name,
            "type": str(item.get("type") or ""),
            "skill": str(item.get("skill") or name),
            "dependencies": [str(dep) for dep in deps] if isinstance(deps, list) else [],
            "test_strategy": str(item.get("test_strategy") or item.get("testStrategy") or ""),
            "covered_surfaces": [str(value) for value in analysis.get("coveredSurfaces", [])] if isinstance(analysis.get("coveredSurfaces"), list) else [],
        }
    return result


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def text_blob(*values: Any) -> str:
    return json.dumps(values, ensure_ascii=False).lower()


def infer_involved_repos(spec: dict[str, Any], registry: dict[str, dict[str, Any]], delivery_plan: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for task in as_list(delivery_plan.get("repo_tasks")):
        if isinstance(task, dict) and task.get("repo"):
            names.append(str(task["repo"]))
    blob = text_blob(spec)
    for name in registry:
        if name.lower() in blob:
            names.append(name)
    explicit = spec.get("repositories") or spec.get("repos") or spec.get("involved_repositories")
    for item in as_list(explicit):
        if isinstance(item, dict) and item.get("repo"):
            names.append(str(item["repo"]))
        elif isinstance(item, str):
            names.append(item)
    if not names and registry:
        names = list(registry)[:1]
    return sorted(dict.fromkeys(name for name in names if name))


def classify_change(repo: str, spec: dict[str, Any], task: dict[str, Any] | None, registry_item: dict[str, Any] | None) -> dict[str, Any]:
    blob = text_blob(spec, task or {}, registry_item or {})
    contract_terms = sorted(term for term in CONTRACT_TERMS if term in blob)
    serial_terms = sorted(term for term in SERIAL_TERMS if term in blob)
    role = str((task or {}).get("role") or "modify")
    repo_type = str((registry_item or {}).get("type") or "")
    if role in {"read_only", "confirm_only", "out_of_scope"}:
        bucket = "parallel_safe"
    elif serial_terms:
        bucket = "serial_required"
    elif contract_terms:
        bucket = "contract_blocked"
    else:
        bucket = "parallel_safe"
    return {
        "repo": repo,
        "role": role,
        "repo_type": repo_type,
        "parallelization": bucket,
        "contract_terms": contract_terms,
        "serial_terms": serial_terms,
        "test_strategy": str((registry_item or {}).get("test_strategy") or ""),
    }


def delivery_tasks_by_repo(delivery_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in as_list(delivery_plan.get("repo_tasks")):
        if isinstance(item, dict) and item.get("repo"):
            result[str(item["repo"])] = item
    return result


def dependency_edges(repos: list[str], registry: dict[str, dict[str, Any]], delivery_plan: dict[str, Any]) -> list[dict[str, Any]]:
    repo_set = set(repos)
    edges: list[dict[str, Any]] = []
    for repo in repos:
        for dep in registry.get(repo, {}).get("dependencies", []):
            if dep in repo_set:
                edges.append({"from": dep, "to": repo, "type": "registry_dependency", "reason": f"{repo} depends on {dep}"})
    ordered = [str(item) for item in as_list(delivery_plan.get("cross_repo_order")) if isinstance(item, str) and item in repo_set]
    for idx, upstream in enumerate(ordered):
        for repo in ordered[idx + 1:]:
            edges.append({"from": upstream, "to": repo, "type": "delivery_order", "reason": "delivery_plan cross_repo_order"})
    unique: dict[tuple[str, str, str], dict[str, Any]] = {}
    for edge in edges:
        unique[(edge["from"], edge["to"], edge["type"])] = edge
    return list(unique.values())


def contract_freeze_points(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    edge_repos = {edge["from"] for edge in edges} | {edge["to"] for edge in edges}
    for node in nodes:
        if node["contract_terms"] or node["repo"] in edge_repos:
            points.append({
                "repo": node["repo"],
                "freeze_before": "consumer implementation" if node["repo"] in {edge["from"] for edge in edges} else "integration testing",
                "terms": node["contract_terms"] or ["cross_repo_dependency"],
                "required_evidence": ["contract summary", "consumer impact confirmation"],
            })
    return points


def integration_gates(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gates = [
        {"gate": "repo_edit_permits", "required_for": [node["repo"] for node in nodes if node["role"] == "modify"], "evidence": "edit_permit per modify repo"},
        {"gate": "contract_freeze", "required_for": sorted({edge["from"] for edge in edges}), "evidence": "provider contract frozen before consumers merge"},
        {"gate": "cross_repo_integration_test", "required_for": sorted({edge["to"] for edge in edges}), "evidence": "provider-consumer integration evidence"},
        {"gate": "release_order_confirmation", "required_for": [node["repo"] for node in nodes], "evidence": "release and rollback order reviewed"},
    ]
    return [gate for gate in gates if gate["required_for"]]


def topo_groups(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    repos = [node["repo"] for node in nodes]
    incoming = {repo: set() for repo in repos}
    outgoing = {repo: set() for repo in repos}
    for edge in edges:
        if edge["from"] in incoming and edge["to"] in incoming:
            incoming[edge["to"]].add(edge["from"])
            outgoing[edge["from"]].add(edge["to"])
    groups: list[dict[str, Any]] = []
    remaining = set(repos)
    order = 1
    while remaining:
        ready = sorted(repo for repo in remaining if not incoming[repo].intersection(remaining))
        if not ready:
            groups.append({"group": order, "repos": sorted(remaining), "mode": "serial_required", "reason": "dependency cycle requires manual ordering"})
            break
        modes = {node["repo"]: node["parallelization"] for node in nodes}
        groups.append({"group": order, "repos": ready, "mode": "parallel_safe" if all(modes.get(repo) == "parallel_safe" for repo in ready) else "gated_parallel", "reason": "all upstream dependencies satisfied"})
        remaining -= set(ready)
        order += 1
    return groups


def has_dependency_cycle(groups: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(group, dict)
        and group.get("mode") == "serial_required"
        and "cycle" in str(group.get("reason") or "").lower()
        for group in groups
    )


def render(doc_id: str, spec: dict[str, Any], registry: dict[str, dict[str, Any]], delivery_plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    repos = infer_involved_repos(spec, registry, delivery_plan)
    tasks = delivery_tasks_by_repo(delivery_plan)
    nodes = [classify_change(repo, spec, tasks.get(repo), registry.get(repo)) for repo in repos]
    edges = dependency_edges(repos, registry, delivery_plan)
    freeze_points = contract_freeze_points(nodes, edges)
    gates = integration_gates(nodes, edges)
    groups = topo_groups(nodes, edges)
    blockers: list[dict[str, Any]] = []
    if len(repos) < 2:
        blockers.append({"source": "repositories", "message": "cross-repo plan requires at least two involved repositories"})
    if registry:
        for repo in repos:
            if repo not in registry:
                blockers.append({"source": repo, "message": "involved repository is missing from project registry"})
    if has_dependency_cycle(groups):
        blockers.append({"source": "dependency_edges", "message": "dependency cycle requires manual serial ordering before parallel execution"})
    if edges and not freeze_points:
        blockers.append({"source": "contract_freeze", "message": "dependency edges require freeze points"})
    graph = {
        "schema": GRAPH_SCHEMA,
        "doc_id": doc_id,
        "repositories": nodes,
        "dependency_edges": edges,
        "parallel_groups": groups,
        "contract_freeze_points": freeze_points,
        "integration_gates": gates,
        "repo_tasks": [
            {
                "repo": node["repo"],
                "state": "planned",
                "parallelization": node["parallelization"],
                "requires_edit_permit": node["role"] == "modify",
                "blocked_by": [edge["from"] for edge in edges if edge["to"] == node["repo"]],
            }
            for node in nodes
        ],
        "blockers": blockers,
        "decision": "blocked" if blockers else "ready",
        "generated_at": now(),
    }
    readiness_blockers = list(blockers)
    for node in nodes:
        if node["role"] == "modify" and not tasks.get(node["repo"]):
            readiness_blockers.append({"source": node["repo"], "message": "modify repository needs a repo delivery task before edit permit"})
    readiness = {
        "schema": READINESS_SCHEMA,
        "doc_id": doc_id,
        "decision": "blocked" if readiness_blockers else "ready",
        "required_before_parallel_execution": ["canonical spec", "cross repo graph", "repo delivery tasks", "contract freeze points", "per-repo edit permits"],
        "repo_states": graph["repo_tasks"],
        "blockers": readiness_blockers,
    }
    release_order = [repo for group in groups for repo in group["repos"]]
    release = {
        "schema": RELEASE_SCHEMA,
        "doc_id": doc_id,
        "decision": "blocked" if blockers else "ready",
        "release_order": release_order,
        "rollback_order": list(reversed(release_order)),
        "integration_test_matrix": [
            {"provider": edge["from"], "consumer": edge["to"], "evidence": "contract or integration test output"}
            for edge in edges
        ],
        "release_gates": gates,
        "blockers": blockers,
    }
    return graph, readiness, release


def example_inputs() -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, Any]]:
    spec = {
        "doc_id": "REQ-CROSS-REPO-EXAMPLE",
        "summary": "Add provider API field and show it in frontend consumer.",
        "acceptance_criteria": ["Provider returns the field", "Consumer renders the field"],
    }
    registry = {
        "frontend": {"name": "frontend", "type": "frontend", "dependencies": ["provider"], "test_strategy": "npm test"},
        "provider": {"name": "provider", "type": "backend", "dependencies": [], "test_strategy": "mvn test"},
        "shared-lib": {"name": "shared-lib", "type": "library", "dependencies": [], "test_strategy": "mvn test"},
    }
    delivery = {
        "repo_tasks": [
            {"repo": "provider", "role": "modify", "tasks": ["add API field"], "allowed_files": ["src/api/ProviderController.java"]},
            {"repo": "frontend", "role": "modify", "tasks": ["render API field"], "allowed_files": ["src/pages/ProviderView.vue"]},
            {"repo": "shared-lib", "role": "confirm_only", "tasks": ["confirm no DTO package change"]},
        ],
        "cross_repo_order": ["provider", "frontend"],
    }
    return spec, registry, delivery


def validate_graph(graph: dict[str, Any]) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    if graph.get("schema") != GRAPH_SCHEMA:
        blockers.append({"source": "schema", "message": f"schema must be {GRAPH_SCHEMA}"})
    repos = graph.get("repositories") if isinstance(graph.get("repositories"), list) else []
    repo_names = {str(item.get("repo")) for item in repos if isinstance(item, dict) and item.get("repo")}
    if len(repo_names) < 2:
        blockers.append({"source": "repositories", "message": "at least two repositories are required"})
    for edge in as_list(graph.get("dependency_edges")):
        if not isinstance(edge, dict):
            blockers.append({"source": "dependency_edges", "message": "edge must be object"})
            continue
        if edge.get("from") not in repo_names or edge.get("to") not in repo_names:
            blockers.append({"source": "dependency_edges", "message": "edge endpoint must reference graph repositories"})
    for key in ["parallel_groups", "integration_gates", "repo_tasks"]:
        if not isinstance(graph.get(key), list):
            blockers.append({"source": key, "message": f"{key} must be a list"})
    if has_dependency_cycle(as_list(graph.get("parallel_groups"))):
        blockers.append({"source": "parallel_groups", "message": "dependency cycle requires manual ordering"})
    graph_decision = str(graph.get("decision") or "")
    if blockers and graph_decision == "ready":
        blockers.append({"source": "decision", "message": "graph decision cannot be ready when validation blockers exist"})
    if graph_decision and graph_decision not in {"ready", "blocked"}:
        blockers.append({"source": "decision", "message": "decision must be ready or blocked"})
    decision = "pass" if not blockers else "block"
    return {"schema": VALIDATION_SCHEMA, "decision": decision, "repo_count": len(repo_names), "blockers": blockers}


def write_outputs(out_dir: Path, graph: dict[str, Any], readiness: dict[str, Any], release: dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "cross_repo_execution_graph.json": graph,
        "cross_repo_readiness.json": readiness,
        "cross_repo_release_plan.json": release,
    }
    for name, data in files.items():
        (out_dir / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate cross-repository execution graph artifacts")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--doc-id", default="")
    p_plan.add_argument("--spec")
    p_plan.add_argument("--registry")
    p_plan.add_argument("--delivery-plan")
    p_plan.add_argument("--out-dir", required=True)
    p_plan.add_argument("--example", action="store_true")
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--graph", required=True)
    args = parser.parse_args()
    if args.cmd == "validate":
        result = validate_graph(read_json(Path(args.graph)))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["decision"] == "pass" else 1
    if args.example:
        spec, registry, delivery = example_inputs()
    else:
        spec = read_json(Path(args.spec)) if args.spec else {}
        registry = load_registry(Path(args.registry)) if args.registry else {}
        delivery = read_json(Path(args.delivery_plan)) if args.delivery_plan else {}
    doc_id = args.doc_id or str(spec.get("doc_id") or delivery.get("doc_id") or "REQ-CROSS-REPO")
    graph, readiness, release = render(doc_id, spec, registry, delivery)
    write_outputs(Path(args.out_dir), graph, readiness, release)
    result = {
        "schema": "codex-cross-repo-planner-run-v1",
        "decision": graph["decision"],
        "out_dir": str(Path(args.out_dir)),
        "artifacts": ["cross_repo_execution_graph.json", "cross_repo_readiness.json", "cross_repo_release_plan.json"],
        "repo_count": len(graph["repositories"]),
        "parallel_group_count": len(graph["parallel_groups"]),
        "blockers": graph["blockers"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
