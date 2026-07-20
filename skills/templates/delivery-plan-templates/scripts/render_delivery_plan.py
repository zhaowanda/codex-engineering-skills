#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any


ROLES = {"modify", "read_only", "confirm_only", "out_of_scope"}
GENERIC_ENTRYPOINT_NAMES = {
    "application.java",
    "main.java",
    "index.js",
    "index.ts",
    "index.tsx",
    "index.jsx",
    "package.json",
    "package-lock.json",
    "vue.config.js",
    "babel.config.js",
    "readme.md",
    "docker-compose.yml",
}
GENERIC_ENTRYPOINT_PARTS = {"assets", "icons", "plugins", "config", "node_modules"}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"JSON root must be object: {path}")
    return data


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def safe_list(value: Any) -> list[str]:
    return [str(item) for item in as_list(value) if str(item).strip()]


def is_generic_entrypoint(path: str) -> bool:
    low = path.strip().lower()
    if not low:
        return False
    parts = set(Path(low).parts)
    return Path(low).name in GENERIC_ENTRYPOINT_NAMES or bool(parts & GENERIC_ENTRYPOINT_PARTS)


def load_project_understanding(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    base = path if path.is_dir() else path.parent
    if not base.exists():
        return {}
    result: dict[str, Any] = {}
    bundle_file = base / "evidence_bundle.json"
    if bundle_file.exists():
        result["evidence_bundle"] = read_json(str(bundle_file))
        for name in ["repository_analysis", "dependency_surface"]:
            file = base / f"{name}.json"
            if file.exists():
                result[name] = read_json(str(file))
        return result
    for name in ["repository_analysis", "dependency_surface", "code_index", "baseline"]:
        file = base / f"{name}.json"
        if file.exists():
            result[name] = read_json(str(file))
    return result


def unquote_yaml_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_project_registry(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    projects: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        match = re.match(r"\s*-\s+name:\s*(.+)\s*$", line)
        if match:
            name = unquote_yaml_value(match.group(1))
            current = {"name": name}
            projects[name] = current
            continue
        if current is None:
            continue
        match = re.match(r"\s*(default_branch|local_path_hint|git_url):\s*(.+)\s*$", line)
        if match:
            current[match.group(1)] = unquote_yaml_value(match.group(2))
    return projects


def registry_candidates() -> list[Path]:
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    return [codex_home / "skills" / "company" / "projects.yaml"]


def project_registry() -> dict[str, dict[str, str]]:
    projects: dict[str, dict[str, str]] = {}
    for path in registry_candidates():
        projects.update(parse_project_registry(path))
    return projects


def is_staging_path(path: str) -> bool:
    return any(part == "_staging" or part.endswith("_staging") for part in Path(path).parts)


def is_git_checkout(path: Path) -> bool:
    return (path / ".git").exists()


def resolve_registered_checkout(entry: dict[str, str], current_root: Path | None = None) -> str:
    hint = str(entry.get("local_path_hint") or entry.get("name") or "").strip()
    if not hint:
        return ""
    hint_path = Path(hint).expanduser()
    candidates: list[Path] = []
    if hint_path.is_absolute():
        candidates.append(hint_path)
    else:
        roots: list[Path] = []
        if current_root:
            roots.append(current_root)
            roots.extend(current_root.parents)
        home = Path.home()
        roots.extend(sorted(path for path in home.glob("*workspace*") if path.is_dir()))
        roots.extend([home / "workspace", home / "workspaces", home])
        seen: set[Path] = set()
        for root in roots:
            try:
                resolved_root = root.expanduser().resolve()
            except OSError:
                continue
            if resolved_root in seen:
                continue
            seen.add(resolved_root)
            candidates.append(resolved_root / hint_path)
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if is_git_checkout(resolved):
            return str(resolved)
    return ""


def project_context(project_understanding: dict[str, Any]) -> dict[str, Any]:
    bundle = project_understanding.get("evidence_bundle", {})
    repo = project_understanding.get("repository_analysis", {})
    deps = project_understanding.get("dependency_surface", {})
    index = project_understanding.get("code_index", {})
    baseline = project_understanding.get("baseline", {})
    project = str(bundle.get("project") or repo.get("project") or baseline.get("project") or "target-repo")
    repo_path = str(bundle.get("repo_root") or index.get("repo_root") or baseline.get("repo_root") or repo.get("repo_root") or "")
    files = [str(item.get("path")) for item in as_list(index.get("files")) if isinstance(item, dict) and item.get("path")]
    entrypoints = [str(item) for item in as_list(repo.get("entrypoint_hints"))]
    if bundle:
        anchors = [item for item in as_list(bundle.get("confirmed_anchors")) if isinstance(item, dict) and item.get("path")]
        files = [str(item["path"]) for item in anchors]
        entrypoints = [str(item["path"]) for item in anchors if item.get("role") != "reference_only"]
    tests = [str(item) for item in as_list(deps.get("test_command_hints"))] or [str(item) for item in as_list(repo.get("test_hints"))]
    return {"project": project, "repo_path": repo_path, "files": files, "entrypoints": entrypoints, "tests": tests}


def repo_responsibilities(architecture: dict[str, Any]) -> list[dict[str, Any]]:
    repos: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in as_list(architecture.get("repo_responsibilities")):
        if not isinstance(item, dict):
            continue
        repo = str(item.get("repo") or "").strip()
        if not repo or repo in seen:
            continue
        seen.add(repo)
        role = str(item.get("role") or "confirm_only")
        repos.append({
            "repo": repo,
            "repo_path": str(item.get("repo_path") or ""),
            "role": role if role in ROLES else "confirm_only",
            "responsibility": str(item.get("responsibility") or item.get("owner_task") or ""),
            "source": "architecture.repo_responsibilities",
        })
    return repos


def topology_by_repo(architecture: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for item in as_list(architecture.get("module_topology")):
        if isinstance(item, dict) and item.get("repo"):
            result.setdefault(str(item["repo"]), []).append(item)
    return result


def tests_from_design(technical: dict[str, Any]) -> list[dict[str, Any]]:
    tests: list[dict[str, Any]] = []
    for idx, item in enumerate(as_list(technical.get("test_strategy"))):
        if isinstance(item, dict):
            tests.append({
                "id": f"T-{idx + 1}",
                "case": str(item.get("case") or item.get("name") or ""),
                "evidence": safe_list(item.get("evidence")),
                "type": str(item.get("type") or "functional"),
            })
    return tests


def acceptance_from_design(technical: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in as_list(technical.get("acceptance_mapping")):
        if isinstance(item, dict):
            items.append({
                "acceptance_id": str(item.get("acceptance_id") or ""),
                "design_refs": safe_list(item.get("design_refs")),
                "evidence_required": safe_list(item.get("evidence_required")),
            })
    return items


def task_steps(repo_name: str, responsibility: str, modules: list[dict[str, Any]], tests: list[dict[str, Any]], allowed_files: list[str], acceptance: list[dict[str, Any]]) -> list[dict[str, Any]]:
    module_refs = [str(item.get("module")) for item in modules if item.get("module")]
    test_refs = [str(item.get("id")) for item in tests if item.get("id")]
    evidence = sorted({item for ac in acceptance for item in safe_list(ac.get("evidence_required"))})
    edit_targets = allowed_files or module_refs
    primary_target = edit_targets[0] if edit_targets else repo_name
    acceptance_ids = [str(item.get("acceptance_id")) for item in acceptance if item.get("acceptance_id")]
    return [
        {"task_id": f"{repo_name}-read", "order": 1, "phase": "read", "summary": f"Read {primary_target} and adjacent tests before editing.", "files_to_read": edit_targets, "files_to_edit": [], "implementation_notes": [f"Inspect {primary_target} to locate the existing behavior for {responsibility or repo_name}.", f"Record current dependencies for modules: {', '.join(module_refs) or primary_target}."], "evidence_to_collect": [f"inspected-files: {', '.join(edit_targets)}"], "rollback_check": "no writes in read phase", "depends_on": [], "blocking_conditions": [f"{primary_target} cannot be located"], "modules": module_refs, "exit_criteria": [f"{primary_target} behavior and dependencies understood"]},
        {"task_id": f"{repo_name}-confirm", "order": 2, "phase": "confirm", "summary": f"Confirm {primary_target} scope against reviewed design.", "files_to_read": edit_targets, "files_to_edit": [], "implementation_notes": [f"Confirm {primary_target} can satisfy acceptance ids {', '.join(acceptance_ids) or 'unmapped AC'} without adding unplanned repositories.", f"Confirm permission, compatibility, and data-flow assumptions before modifying {primary_target}."], "evidence_to_collect": [f"scope-confirmation for {primary_target}"], "rollback_check": "scope change requires plan update, not ad hoc editing", "depends_on": [f"{repo_name}-read"], "blocking_conditions": [f"{primary_target} does not match the reviewed module topology"], "modules": module_refs, "exit_criteria": ["scope still matches architecture responsibilities"]},
        {"task_id": f"{repo_name}-edit", "order": 3, "phase": "edit", "summary": responsibility or f"Implement scoped change in {primary_target}.", "files_to_read": edit_targets, "files_to_edit": edit_targets, "implementation_notes": [f"Apply the requirement behavior in {primary_target}.", f"Keep edits inside {', '.join(edit_targets)} unless the plan is updated.", f"Preserve reviewed contracts and permission checks for acceptance ids {', '.join(acceptance_ids) or 'unmapped AC'}."], "evidence_to_collect": [f"git diff for {', '.join(edit_targets)}"], "rollback_check": f"revert changes to {', '.join(edit_targets)} and redeploy previous {repo_name} artifact", "depends_on": [f"{repo_name}-confirm"], "blocking_conditions": ["required edit falls outside allowed_files"], "modules": module_refs, "change_type": sorted({str(item.get("change_type")) for item in modules if item.get("change_type")}), "exit_criteria": [f"diff only touches {', '.join(edit_targets)}"]},
        {"task_id": f"{repo_name}-test", "order": 4, "phase": "test", "summary": f"Run validation for {primary_target} and mapped acceptance checks.", "files_to_read": edit_targets, "files_to_edit": [], "implementation_notes": [f"Run repo test commands against changes in {primary_target}.", f"Verify evidence for acceptance ids {', '.join(acceptance_ids) or 'unmapped AC'}."], "evidence_to_collect": evidence or ["test command output"], "rollback_check": "failed validation blocks release", "depends_on": [f"{repo_name}-edit"], "blocking_conditions": ["required local test command unavailable"], "test_refs": test_refs, "exit_criteria": ["required tests pass"]},
        {"task_id": f"{repo_name}-evidence", "order": 5, "phase": "evidence", "summary": f"Capture command logs and acceptance evidence for {primary_target}.", "files_to_read": [], "files_to_edit": [], "implementation_notes": [f"Attach test logs and acceptance evidence for {primary_target}.", f"Reference acceptance ids {', '.join(acceptance_ids) or 'unmapped AC'} in the delivery artifact."], "evidence_to_collect": evidence or ["review log", "test log"], "rollback_check": "missing evidence blocks release", "depends_on": [f"{repo_name}-test"], "blocking_conditions": ["acceptance evidence cannot be produced"], "test_refs": test_refs, "exit_criteria": ["evidence artifacts are attached to delivery"]},
        {"task_id": f"{repo_name}-rollback", "order": 6, "phase": "rollback", "summary": f"Verify rollback path for {primary_target}.", "files_to_read": edit_targets, "files_to_edit": [], "implementation_notes": [f"Confirm reverting {primary_target} is sufficient for rollback.", f"Confirm no data/config rollback is required beyond {repo_name} artifact rollback."], "evidence_to_collect": [f"rollback verification for {primary_target}"], "rollback_check": f"previous {repo_name} artifact or commit can be restored", "depends_on": [f"{repo_name}-evidence"], "blocking_conditions": ["rollback owner or artifact is unknown"], "modules": module_refs, "exit_criteria": ["rollback owner and steps are known"]},
    ]


def allowed_files_hint(repo: str, architecture: dict[str, Any]) -> list[str]:
    hints: list[str] = []
    for item in topology_by_repo(architecture).get(repo, []):
        module = str(item.get("module") or "").strip("/")
        if module:
            hints.append(module)
    return sorted(set(hints))


def read_first_hint(repo: str, architecture: dict[str, Any], ctx: dict[str, Any]) -> list[str]:
    hints = allowed_files_hint(repo, architecture)
    if ctx["files"] and repo in {ctx["project"], "target-repo"}:
        hints = [*hints, *ctx["entrypoints"], *ctx["files"][:5]]
    return narrow_allowed_files(hints)


def narrow_allowed_files(paths: list[str]) -> list[str]:
    concrete: list[str] = []
    for item in paths:
        path = str(item).strip().strip("/")
        if not path:
            continue
        parts = Path(path).parts
        if len(parts) <= 1 and "." not in Path(path).name:
            continue
        if is_generic_entrypoint(path):
            continue
        concrete.append(path)
    return sorted(set(concrete))


def render_from_design(
    doc_id: str,
    technical: dict[str, Any],
    architecture: dict[str, Any],
    project_understanding: dict[str, Any] | None = None,
    design_review: dict[str, Any] | None = None,
    test_design: dict[str, Any] | None = None,
    test_data_plan: dict[str, Any] | None = None,
    cross_repo_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ctx = project_context(project_understanding or {})
    technical_gate = technical.get("requirements_understanding_gate") if isinstance(technical.get("requirements_understanding_gate"), dict) else {}
    architecture_gate = architecture.get("requirements_understanding_gate") if isinstance(architecture.get("requirements_understanding_gate"), dict) else {}
    source_design_gate = architecture_gate or technical_gate
    repos = repo_responsibilities(architecture)
    topology = topology_by_repo(architecture)
    acceptance = acceptance_from_design(technical)
    tests = tests_from_design(technical)
    registry = project_registry()
    repo_tasks: list[dict[str, Any]] = []
    open_gates: list[str] = []
    technical_source_locations = technical.get("source_location_evidence")
    architecture_source_locations = architecture.get("source_location_evidence")
    if isinstance(technical_source_locations, dict):
        source_locations: dict[str, Any] = technical_source_locations
    elif isinstance(architecture_source_locations, dict):
        source_locations = architecture_source_locations
    else:
        source_locations = {}
    confirmed_paths = {
        str(item.get("path")) for item in as_list(source_locations.get("confirmed_anchors"))
        if isinstance(item, dict) and item.get("path") and item.get("role", "modify_candidate") != "reference_only"
    }
    rejected_paths = {
        str(item.get("path")) for item in as_list(source_locations.get("rejected_candidates"))
        if isinstance(item, dict) and item.get("path")
    }
    if source_locations and (source_locations.get("decision") != "pass" or not confirmed_paths):
        open_gates.append("source_location_evidence: no requirement-specific source location is confirmed")
    if source_design_gate and source_design_gate.get("design_allowed") is False:
        open_gates.append("requirements_understanding_gate: design is blocked until requirement clarification is resolved")
    if source_design_gate and source_design_gate.get("implementation_allowed") is False:
        open_gates.append("requirements_understanding_gate: implementation is blocked until requirement clarification is resolved")
    for repo in repos:
        repo_name = repo["repo"]
        role = repo["role"]
        planned_repo_path = repo["repo_path"] or (ctx["repo_path"] if repo_name in {ctx["project"], "target-repo"} else "")
        registry_entry = registry.get(repo_name, {})
        registered_checkout = resolve_registered_checkout(registry_entry, Path.cwd()) if registry_entry else ""
        repo_path = registered_checkout if role == "modify" and registered_checkout else planned_repo_path
        modules = topology.get(repo_name, [])
        allowed = allowed_files_hint(repo_name, architecture)
        allowed = narrow_allowed_files(allowed)
        if source_locations:
            rejected_in_scope = sorted(path for path in allowed if path in rejected_paths)
            unconfirmed_in_scope = sorted(path for path in allowed if path not in confirmed_paths)
            if rejected_in_scope:
                open_gates.append(f"{repo_name}: rejected source candidates cannot enter allowed_files: {', '.join(rejected_in_scope)}")
            if unconfirmed_in_scope:
                open_gates.append(f"{repo_name}: allowed_files lack source confirmation: {', '.join(unconfirmed_in_scope)}")
            allowed = [path for path in allowed if path in confirmed_paths]
        read_first = read_first_hint(repo_name, architecture, ctx)
        test_commands = ctx["tests"] if repo_name in {ctx["project"], "target-repo"} else []
        task = {
            "repo": repo_name,
            "repo_path": repo_path,
            "role": role,
            "responsibility": repo["responsibility"],
            "base_branch": registry_entry.get("default_branch", ""),
            "git_preparation": {
                "required_before_edit": ["git fetch --all --prune", "git pull --ff-only", "create or switch to requirement branch", "verify clean worktree"],
                "branch_naming_hint": f"feature/{doc_id.lower()}",
            } if role == "modify" else {},
            "tasks": task_steps(repo_name, repo["responsibility"], modules, tests, allowed, acceptance) if role == "modify" else [
                {
                    "task_id": f"{repo_name}-confirm",
                    "phase": "confirm",
                    "summary": repo["responsibility"] or "Confirm repository impact",
                    "modules": [str(item.get("module")) for item in modules if item.get("module")],
                    "change_type": sorted({str(item.get("change_type")) for item in modules if item.get("change_type")}),
                }
            ],
            "read_first": read_first,
            "allowed_files": allowed if role == "modify" else [],
            "test_commands": test_commands,
            "acceptance_evidence": acceptance,
            "risks": [{"risk": "scope drift during implementation", "mitigation": "enforce allowed_files with edit-readiness and workspace-write-guard"}] if role == "modify" else [],
            "rollback": [{"step": "revert repo changes and redeploy previous artifact", "data_risk": "use architecture rollback_strategy for data/config changes"}] if role == "modify" else [],
        }
        if role == "modify":
            if not repo_path:
                open_gates.append(f"{repo_name}: repo_path is required before git prepare-plan")
            if planned_repo_path and is_staging_path(planned_repo_path) and not registered_checkout:
                open_gates.append(f"{repo_name}: repo_path points to _staging; resolve the registered project checkout before git prepare-plan")
            if not task["allowed_files"]:
                open_gates.append(f"{repo_name}: allowed_files should be narrowed before edit permit")
            if not tests:
                open_gates.append(f"{repo_name}: test strategy is missing")
        repo_tasks.append(task)
    if not repos:
        open_gates.append("architecture.repo_responsibilities is empty")
    release_order = [item["repo"] for item in repo_tasks if item["role"] == "modify"]
    rollback_order = list(reversed(release_order))
    modify_task_refs = [
        task_ref
        for repo in repo_tasks
        if repo.get("role") == "modify"
        for task_ref in [f"{repo['repo']}-test", f"{repo['repo']}-evidence"]
    ]
    return {
        "schema": "codex-delivery-plan-v1",
        "doc_id": doc_id,
        "source": {
            "technical_design_doc_id": technical.get("doc_id", ""),
            "architecture_design_doc_id": architecture.get("doc_id", ""),
            "design_review_decision": (design_review or {}).get("decision", ""),
            "test_design_decision": (test_design or {}).get("decision", ""),
            "test_data_plan_decision": (test_data_plan or {}).get("decision", ""),
            "cross_repo_readiness_decision": (cross_repo_readiness or {}).get("decision", ""),
        },
        "source_design_gate": source_design_gate,
        "source_location_evidence": source_locations,
        "repo_tasks": repo_tasks,
        "parallel_groups": [
            {
                "group": 1,
                "repos": [item["repo"] for item in repo_tasks if item.get("role") == "modify"],
                "mode": "parallel_safe" if len([item for item in repo_tasks if item.get("role") == "modify"]) <= 1 else "requires_cross_repo_graph",
                "source": "delivery-plan-templates",
            }
        ],
        "dependency_edges": [
            {"from": dep, "to": item.get("repo"), "type": "module_dependency"}
            for item in as_list(architecture.get("module_topology"))
            if isinstance(item, dict) and item.get("repo")
            for dep in safe_list(item.get("depends_on"))
        ],
        "integration_gates": [
            {"gate": "contract_freeze", "required_when": "dependency_edges or API/config/schema changes exist"},
            {"gate": "cross_repo_integration_test", "required_when": "more than one modify repository exists"},
        ],
        "contract_freeze_points": [
            {"repo": item.get("repo"), "module": item.get("module"), "freeze_before": "consumer implementation"}
            for item in as_list(architecture.get("module_topology"))
            if isinstance(item, dict) and item.get("repo") and any(term in str(item).lower() for term in ["api", "contract", "schema", "event", "config", "db"])
        ],
        "cross_repo_order": release_order,
        "validation_plan": {
            "test_strategy": tests,
            "acceptance": acceptance,
            "required_evidence": sorted({evidence for item in acceptance for evidence in item.get("evidence_required", [])}),
            "acceptance_task_mapping": [
                {
                    "acceptance_id": item.get("acceptance_id", ""),
                    "task_refs": modify_task_refs,
                    "evidence_required": item.get("evidence_required", []),
                }
                for item in acceptance
            ],
        },
        "release_plan": {
            "release_order": release_order,
            "environment_order": ["dev", "test", "staging", "production"],
            "release_gate": "all repo tasks complete, tests pass, write guard audit ready, review gate pass",
        },
        "rollback_plan": {
            "rollback_order": rollback_order,
            "source": architecture.get("rollback_strategy", []),
        },
        "open_gates": open_gates,
        "decision": "ready" if not open_gates else "needs_completion",
        "generated_at": now(),
    }


def example_plan(doc_id: str) -> dict[str, Any]:
    technical = {
        "doc_id": doc_id,
        "acceptance_mapping": [{"acceptance_id": "AC-1", "design_refs": ["checkout summary"], "evidence_required": ["browser screenshot"]}],
        "test_strategy": [{"case": "discount breakdown visible", "evidence": ["browser screenshot"], "type": "ui"}],
    }
    architecture = {
        "doc_id": doc_id,
        "repo_responsibilities": [
            {"repo": "web-app", "repo_path": "/workspace/web-app", "role": "modify", "responsibility": "render discount rows"},
            {"repo": "pricing-service", "repo_path": "/workspace/pricing-service", "role": "confirm_only", "responsibility": "confirm contract unchanged"},
        ],
        "module_topology": [
            {"repo": "web-app", "module": "src/checkout/summary", "responsibility": "display discount rows", "depends_on": ["pricing-service"], "boundary_rule": "read-only API consumer", "change_type": "modify"}
        ],
        "rollback_strategy": [{"repo": "web-app", "steps": ["revert commit", "redeploy"], "data_risk": "none"}],
    }
    return render_from_design(doc_id, technical, architecture)


def validate(plan: dict[str, Any]) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if plan.get("schema") != "codex-delivery-plan-v1":
        issues.append("schema must be codex-delivery-plan-v1")
    if not plan.get("doc_id"):
        issues.append("doc_id is required")
    repo_tasks = as_list(plan.get("repo_tasks"))
    if not repo_tasks:
        issues.append("repo_tasks is required")
    repo_names: set[str] = set()
    modify_repo_count = 0
    for idx, task in enumerate(repo_tasks):
        if not isinstance(task, dict):
            issues.append(f"repo_tasks[{idx}] must be object")
            continue
        role = task.get("role")
        repo = task.get("repo")
        if repo:
            repo_names.add(str(repo))
        if role not in ROLES:
            issues.append(f"repo_tasks[{idx}].role invalid")
        if not repo:
            issues.append(f"repo_tasks[{idx}].repo is required")
        if role == "modify":
            modify_repo_count += 1
            if not task.get("repo_path"):
                issues.append(f"{repo}: modify repo requires repo_path")
            elif is_staging_path(str(task.get("repo_path"))):
                issues.append(f"{repo}: modify repo_path must not point to _staging")
            if not task.get("allowed_files"):
                issues.append(f"{repo}: modify repo requires allowed_files")
            if not task.get("tasks"):
                issues.append(f"{repo}: modify repo requires tasks")
    for key in ["validation_plan", "release_plan", "rollback_plan"]:
        if not isinstance(plan.get(key), dict):
            issues.append(f"{key} is required")
    for key in ["parallel_groups", "dependency_edges", "integration_gates", "contract_freeze_points"]:
        if key in plan and not isinstance(plan.get(key), list):
            issues.append(f"{key} must be a list")
    for idx, edge in enumerate(as_list(plan.get("dependency_edges"))):
        if not isinstance(edge, dict):
            issues.append(f"dependency_edges[{idx}] must be object")
            continue
        if edge.get("from") not in repo_names or edge.get("to") not in repo_names:
            issues.append(f"dependency_edges[{idx}] endpoints must reference repo_tasks")
    for idx, point in enumerate(as_list(plan.get("contract_freeze_points"))):
        if not isinstance(point, dict):
            issues.append(f"contract_freeze_points[{idx}] must be object")
            continue
        if point.get("repo") not in repo_names:
            issues.append(f"contract_freeze_points[{idx}].repo must reference repo_tasks")
    if modify_repo_count > 1:
        groups = [item for item in as_list(plan.get("parallel_groups")) if isinstance(item, dict)]
        if not any(item.get("mode") in {"requires_cross_repo_graph", "gated_parallel", "serial_required"} for item in groups):
            issues.append("multiple modify repositories require a cross-repo graph or gated/serial parallel group")
    if plan.get("decision") not in {"ready", "needs_completion"}:
        issues.append("decision must be ready/needs_completion")
    return not issues, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Render or validate delivery plan artifacts")
    sub = parser.add_subparsers(dest="cmd")
    p_validate = sub.add_parser("validate")
    p_validate.add_argument("--file", required=True)
    parser.add_argument("--doc-id")
    parser.add_argument("--technical-design")
    parser.add_argument("--architecture-design")
    parser.add_argument("--project-understanding")
    parser.add_argument("--design-review")
    parser.add_argument("--test-design")
    parser.add_argument("--test-data-plan")
    parser.add_argument("--cross-repo-readiness")
    parser.add_argument("--example", action="store_true")
    parser.add_argument("--out")
    args = parser.parse_args()

    if args.cmd == "validate":
        plan = read_json(args.file)
        valid, issues = validate(plan)
        print(json.dumps({"schema": "codex-delivery-plan-validation-v1", "valid": valid, "issues": issues}, ensure_ascii=False, indent=2))
        return 0 if valid else 1
    if not args.out:
        raise SystemExit("--out is required")
    doc_id = args.doc_id or "REQ-UNSET"
    if args.example:
        plan = example_plan(doc_id)
    else:
        if not args.technical_design or not args.architecture_design:
            raise SystemExit("--technical-design and --architecture-design are required unless --example is used")
        plan = render_from_design(
            doc_id,
            read_json(args.technical_design),
            read_json(args.architecture_design),
            load_project_understanding(Path(args.project_understanding)) if args.project_understanding else None,
            read_json(args.design_review) if args.design_review else None,
            read_json(args.test_design) if args.test_design else None,
            read_json(args.test_data_plan) if args.test_data_plan else None,
            read_json(args.cross_repo_readiness) if args.cross_repo_readiness else None,
        )
    write_json(args.out, plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0 if plan.get("decision") == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
