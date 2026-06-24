#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-framework-config-validation-v1"
FRAMEWORK_SCHEMA = "codex-engineering-skills-framework-v1"
PROJECT_REGISTRY_SCHEMA = "codex-project-registry-v1"
REQUIRED_LANES = {
    "standard_requirement": ["doc_id", "spec", "technical_design", "architecture_design", "delivery_plan", "git", "edit_permit", "implementation", "review", "test", "release"],
    "bugfix": ["doc_id", "reproduction", "git", "edit_permit", "implementation", "review", "test"],
    "hotfix": ["doc_id", "git", "implementation", "review", "test", "release"],
}
PROJECT_TYPES = {"frontend", "backend", "fullstack", "library", "service", "docs", "infra", "mobile", "other"}


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception:
        return load_restricted_yaml(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_restricted_yaml(path: Path) -> dict[str, Any]:
    lines: list[tuple[int, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lines.append((len(raw) - len(raw.lstrip(" ")), raw.strip()))

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines):
            return {}, index
        container: Any = [] if lines[index][1].startswith("- ") else {}
        while index < len(lines):
            current_indent, text = lines[index]
            if current_indent < indent:
                break
            if current_indent > indent:
                break
            if text.startswith("- "):
                if not isinstance(container, list):
                    break
                item = text[2:].strip()
                index += 1
                if ":" in item:
                    key, value = item.split(":", 1)
                    entry: dict[str, Any] = {}
                    if value.strip():
                        entry[key.strip()] = parse_scalar(value.strip())
                    else:
                        child, index = parse_block(index, indent + 2)
                        entry[key.strip()] = child
                    while index < len(lines) and lines[index][0] > indent:
                        child_indent, child_text = lines[index]
                        if child_indent != indent + 2 or child_text.startswith("- ") or ":" not in child_text:
                            break
                        child_key, child_value = child_text.split(":", 1)
                        index += 1
                        if child_value.strip():
                            entry[child_key.strip()] = parse_scalar(child_value.strip())
                        else:
                            child, index = parse_block(index, child_indent + 2)
                            entry[child_key.strip()] = child
                    container.append(entry)
                else:
                    container.append(parse_scalar(item))
                continue
            if not isinstance(container, dict) or ":" not in text:
                break
            key, value = text.split(":", 1)
            index += 1
            if value.strip():
                container[key.strip()] = parse_scalar(value.strip())
            else:
                child, index = parse_block(index, indent + 2)
                container[key.strip()] = child
        return container, index

    parsed, _ = parse_block(0, lines[0][0] if lines else 0)
    return parsed if isinstance(parsed, dict) else {}


def parse_scalar(value: str) -> Any:
    value = value.strip().strip('"').strip("'")
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    try:
        return int(value)
    except ValueError:
        return value


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def has_env_placeholder(value: Any) -> bool:
    return isinstance(value, str) and bool(re.search(r"\$\{[^}]+}", value))


def is_placeholder_path(value: str) -> bool:
    return value.startswith("/path/to/") or value in {".", "./", ""}


def is_inside(path_text: str, root: Path) -> bool:
    if has_env_placeholder(path_text) or is_placeholder_path(path_text):
        return False
    try:
        path = Path(os.path.expandvars(path_text)).expanduser().resolve()
        root_resolved = root.resolve()
        return path == root_resolved or root_resolved in path.parents
    except Exception:
        return False


def validate_framework(framework: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if framework.get("schema") != FRAMEWORK_SCHEMA:
        blockers.append({"source": "framework.schema", "message": f"schema must be {FRAMEWORK_SCHEMA}"})
    for section in ["paths", "delivery", "quality", "privacy"]:
        if not isinstance(framework.get(section), dict):
            blockers.append({"source": f"framework.{section}", "message": f"{section} section is required"})

    paths = framework.get("paths", {}) if isinstance(framework.get("paths"), dict) else {}
    for key in ["skills_root", "artifact_root"]:
        if not paths.get(key):
            blockers.append({"source": f"paths.{key}", "message": f"{key} is required"})
    for key, value in paths.items():
        if has_env_placeholder(value):
            warnings.append({"source": f"paths.{key}", "message": "path contains environment placeholder; verify it is set at runtime", "value": value})

    delivery = framework.get("delivery", {}) if isinstance(framework.get("delivery"), dict) else {}
    branches = as_list(delivery.get("default_branch_candidates"))
    if not branches:
        blockers.append({"source": "delivery.default_branch_candidates", "message": "default branch candidates are required"})
    required_gates = delivery.get("required_gates", {}) if isinstance(delivery.get("required_gates"), dict) else {}
    for lane, gates in REQUIRED_LANES.items():
        configured = [str(item) for item in as_list(required_gates.get(lane))]
        if not configured:
            blockers.append({"source": f"delivery.required_gates.{lane}", "message": "delivery lane gate list is required"})
            continue
        missing = [gate for gate in gates if gate not in configured]
        if missing:
            blockers.append({"source": f"delivery.required_gates.{lane}", "message": "required gates are missing", "missing_gates": missing})

    quality = framework.get("quality", {}) if isinstance(framework.get("quality"), dict) else {}
    min_score = quality.get("design_minimum_score")
    expert_score = quality.get("design_expert_score")
    if not isinstance(min_score, int) or min_score < 0 or min_score > 100:
        blockers.append({"source": "quality.design_minimum_score", "message": "design_minimum_score must be an integer from 0 to 100"})
    if not isinstance(expert_score, int) or expert_score < 0 or expert_score > 100:
        blockers.append({"source": "quality.design_expert_score", "message": "design_expert_score must be an integer from 0 to 100"})
    if isinstance(min_score, int) and isinstance(expert_score, int) and expert_score < min_score:
        blockers.append({"source": "quality.design_expert_score", "message": "design_expert_score must be greater than or equal to design_minimum_score"})
    return blockers, warnings


def validate_project_registry(registry: dict[str, Any], open_core_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    if not registry:
        return blockers, warnings
    if registry.get("schema") != PROJECT_REGISTRY_SCHEMA:
        blockers.append({"source": "project_registry.schema", "message": f"schema must be {PROJECT_REGISTRY_SCHEMA}"})
    projects = registry.get("projects")
    if not isinstance(projects, list) or not projects:
        blockers.append({"source": "project_registry.projects", "message": "projects must be a non-empty list"})
        return blockers, warnings

    seen_names: set[str] = set()
    for index, project in enumerate(projects):
        if not isinstance(project, dict):
            blockers.append({"source": f"projects[{index}]", "message": "project entry must be an object"})
            continue
        name = str(project.get("name") or "")
        source = f"projects[{name or index}]"
        if not name:
            blockers.append({"source": source, "message": "project name is required"})
        elif name in seen_names:
            blockers.append({"source": source, "message": "project name must be unique"})
        seen_names.add(name)
        for key in ["root", "type", "default_branch", "skill"]:
            if not project.get(key):
                blockers.append({"source": f"{source}.{key}", "message": f"{key} is required"})
        project_type = str(project.get("type") or "")
        if project_type and project_type not in PROJECT_TYPES:
            warnings.append({"source": f"{source}.type", "message": "project type is not a known generic type", "value": project_type})
        root = str(project.get("root") or "")
        if root:
            if is_placeholder_path(root):
                warnings.append({"source": f"{source}.root", "message": "project root is a placeholder and must be replaced in a private overlay"})
            elif is_inside(root, open_core_root):
                blockers.append({"source": f"{source}.root", "message": "project root must not point inside the open-core repository"})
        if not project.get("test_strategy"):
            warnings.append({"source": f"{source}.test_strategy", "message": "test_strategy is recommended"})
        for related in as_list(project.get("related_projects")):
            if related and str(related) not in seen_names:
                warnings.append({"source": f"{source}.related_projects", "message": "related project is not declared before this entry", "related_project": related})
    return blockers, warnings


def validate(framework_path: Path, project_registry_path: Path | None = None, open_core_root: Path | None = None) -> dict[str, Any]:
    open_core = open_core_root or framework_path.resolve().parents[1]
    framework = load_yaml(framework_path)
    blockers, warnings = validate_framework(framework)
    registry_summary: dict[str, Any] = {"present": False}
    if project_registry_path:
        registry = load_yaml(project_registry_path)
        reg_blockers, reg_warnings = validate_project_registry(registry, open_core)
        blockers.extend(reg_blockers)
        warnings.extend(reg_warnings)
        registry_summary = {
            "present": True,
            "project_count": len(as_list(registry.get("projects"))) if registry else 0,
            "path": str(project_registry_path),
        }
    decision = "block" if blockers else "warn" if warnings else "pass"
    return {
        "schema": SCHEMA,
        "decision": decision,
        "blockers": blockers,
        "warnings": warnings,
        "summary": {
            "framework": str(framework_path),
            "open_core_root": str(open_core),
            "project_registry": registry_summary,
        },
        "next_action": "Fix blocking configuration issues before running delivery workflow." if blockers else "Configuration is usable; resolve warnings before team rollout." if warnings else "Configuration is ready.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate framework and private overlay configuration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--framework", required=True)
    validate_parser.add_argument("--project-registry")
    validate_parser.add_argument("--open-core-root")
    validate_parser.add_argument("--out")
    args = parser.parse_args()

    result = validate(
        framework_path=Path(args.framework),
        project_registry_path=Path(args.project_registry) if args.project_registry else None,
        open_core_root=Path(args.open_core_root) if args.open_core_root else None,
    )
    if args.out:
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
