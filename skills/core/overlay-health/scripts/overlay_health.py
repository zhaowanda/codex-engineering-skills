#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


def load_yaml_like(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def asset_freshness(path: Path, source: str, freshness_days: int, warnings: list[dict[str, Any]]) -> None:
    data = load_json(path)
    generated_at = parse_timestamp(data.get("generated_at"))
    source_revision = data.get("source_revision")
    if not generated_at and not source_revision:
        warnings.append({"source": source, "message": f"{path.name} missing generated_at/source_revision freshness metadata"})
        return
    if generated_at:
        age_days = (datetime.now(timezone.utc) - generated_at).days
        if age_days > freshness_days:
            warnings.append({"source": source, "message": f"{path.name} is {age_days} days old; refresh recommended", "age_days": age_days, "freshness_days": freshness_days})


def first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def path_candidates(overlay_root: Path, raw: Any, fallback: str) -> list[Path]:
    value = str(raw or fallback).strip()
    if not value:
        value = fallback
    path = Path(value)
    candidates = [path if path.is_absolute() else overlay_root / path]
    if value.startswith("skills/"):
        stripped = value.removeprefix("skills/")
        candidates.append(overlay_root / stripped)
    else:
        candidates.append(overlay_root / "skills" / value)
    return list(dict.fromkeys(candidates))


def project_skill_candidates(overlay_root: Path, project: dict[str, Any], name: str) -> list[Path]:
    assets = project.get("assets") if isinstance(project.get("assets"), dict) else {}
    raw_skill = assets.get("skill") or project.get("skill_path")
    skill_name = str(project.get("skill") or name)
    candidates = path_candidates(overlay_root, raw_skill, f"skills/{skill_name}/SKILL.md")
    candidates.extend([
        overlay_root / skill_name / "SKILL.md",
        overlay_root / name / "SKILL.md",
        overlay_root / "skills" / skill_name / "SKILL.md",
        overlay_root / "skills" / name / "SKILL.md",
    ])
    return list(dict.fromkeys(candidates))


def normalize_json_project(project: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(project)
    if "default_branch" not in normalized and project.get("defaultBranch"):
        normalized["default_branch"] = project.get("defaultBranch")
    if "dependencies" not in normalized and isinstance(project.get("relatedProjects"), list):
        normalized["dependencies"] = project.get("relatedProjects")
    analysis = project.get("analysis") if isinstance(project.get("analysis"), dict) else {}
    assets = dict(project.get("assets") if isinstance(project.get("assets"), dict) else {})
    if analysis.get("codeIndex") and not assets.get("index"):
        assets["index"] = analysis.get("codeIndex")
    if analysis.get("baseline") and not assets.get("baseline"):
        assets["baseline"] = analysis.get("baseline")
    skill_name = str(project.get("skill") or project.get("name") or "")
    if skill_name and not assets.get("skill"):
        assets["skill"] = f"skills/{skill_name}/SKILL.md"
    if assets:
        normalized["assets"] = assets
    return normalized


def load_registry_projects(overlay_root: Path, blockers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    projects_by_name: dict[str, dict[str, Any]] = {}
    sources: list[str] = []
    yaml_path = overlay_root / "projects.yaml"
    json_path = overlay_root / "registry" / "projects.json"
    if yaml_path.exists():
        registry = load_yaml_like(yaml_path)
        yaml_projects = registry.get("projects", []) if isinstance(registry.get("projects"), list) else []
        for project in yaml_projects:
            if isinstance(project, dict) and project.get("name"):
                projects_by_name[str(project["name"])] = dict(project)
        sources.append("projects.yaml")
    if json_path.exists():
        registry = load_json(json_path)
        json_projects = registry.get("projects", []) if isinstance(registry.get("projects"), list) else []
        for project in json_projects:
            if not isinstance(project, dict) or not project.get("name"):
                continue
            normalized = normalize_json_project(project)
            name = str(normalized["name"])
            merged = dict(normalized)
            merged.update(projects_by_name.get(name, {}))
            merged_assets = dict(normalized.get("assets", {}) if isinstance(normalized.get("assets"), dict) else {})
            merged_assets.update(projects_by_name.get(name, {}).get("assets", {}) if isinstance(projects_by_name.get(name, {}).get("assets"), dict) else {})
            if merged_assets:
                merged["assets"] = merged_assets
            projects_by_name[name] = merged
        sources.append("registry/projects.json")
    if not sources:
        blockers.append({"source": "projects.yaml", "message": "project registry is required"})
    return list(projects_by_name.values()), sources


DEFAULT_PROJECT_SKILL_SIGNALS = {
    "ownership": ["owner", "ownership", "boundary", "module"],
    "commands": ["command", "build", "run", "启动", "命令"],
    "test_commands": ["test", "pytest", "npm test", "mvn test", "测试"],
    "index_reference": ["code-index", "code_index", "indexes/"],
}


def normalize_policy(policy: dict[str, Any] | None) -> dict[str, Any]:
    policy = policy or {}
    raw_sections = policy.get("project_skill_required_sections")
    sections = raw_sections if isinstance(raw_sections, dict) else DEFAULT_PROJECT_SKILL_SIGNALS
    return {
        "freshness_days": int(policy.get("freshness_days") or 30),
        "project_skill_required_sections": {
            str(name): [str(term).lower() for term in as_list(terms)]
            for name, terms in sections.items()
            if as_list(terms)
        },
        "block_on_missing_sections": {str(item) for item in as_list(policy.get("block_on_missing_sections"))},
    }


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def check_project_skill_content(skill_path: Path, source: str, blockers: list[dict[str, Any]], warnings: list[dict[str, Any]], policy: dict[str, Any]) -> None:
    if not skill_path.exists():
        return
    text = skill_path.read_text(encoding="utf-8", errors="ignore")
    lowered = text.lower()
    required_signals = policy["project_skill_required_sections"]
    missing = [
        name
        for name, terms in required_signals.items()
        if not any(term in lowered for term in terms)
    ]
    for name in missing:
        warnings.append({"source": source, "message": f"project skill missing {name} guidance"})
    policy_blockers = policy["block_on_missing_sections"]
    if policy_blockers and policy_blockers.intersection(missing):
        blockers.append({"source": source, "message": f"project skill missing required policy sections: {', '.join(sorted(policy_blockers.intersection(missing)))}"})
    elif {"ownership", "index_reference"}.issubset(set(missing)):
        blockers.append({"source": source, "message": "project skill lacks ownership and code index guidance"})


def check(overlay_root: Path, freshness_days: int = 30, policy: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_policy = normalize_policy(policy)
    freshness_days = int(normalized_policy.get("freshness_days") or freshness_days)
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    projects, registry_sources = load_registry_projects(overlay_root, blockers)
    checked_assets: list[dict[str, Any]] = []
    project_skill_count = 0
    skipped_skill_count = 0
    for project in projects:
        if not isinstance(project, dict):
            continue
        name = str(project.get("name") or "")
        if not name:
            blockers.append({"source": "projects", "message": "project name is required"})
            continue
        project_type = str(project.get("skill_type") or project.get("kind") or "project")
        if project_type in {"tool", "governor", "helper"}:
            skipped_skill_count += 1
            continue
        project_skill_count += 1
        skill_path = first_existing(project_skill_candidates(overlay_root, project, name))
        if not skill_path:
            blockers.append({"source": name, "message": "project skill missing"})
        else:
            check_project_skill_content(skill_path, name, blockers, warnings, normalized_policy)
        assets = project.get("assets") if isinstance(project.get("assets"), dict) else {}
        index_path = first_existing(path_candidates(overlay_root, assets.get("index"), f"indexes/{name}.code_index.json"))
        baseline_path = first_existing(path_candidates(overlay_root, assets.get("baseline"), f"baseline/{name}.baseline.json"))
        fallback_indexes = list((overlay_root / "indexes").glob(f"{name}*.json"))
        fallback_baselines = list((overlay_root / "baseline").glob(f"{name}*.json"))
        if not index_path and not fallback_indexes:
            blockers.append({"source": name, "message": "project index missing"})
        else:
            resolved_index = index_path if index_path else fallback_indexes[0]
            checked_assets.append({"project": name, "type": "index", "path": str(resolved_index.relative_to(overlay_root) if resolved_index.is_relative_to(overlay_root) else resolved_index)})
            asset_freshness(resolved_index, name, freshness_days, warnings)
        if not baseline_path and not fallback_baselines:
            blockers.append({"source": name, "message": "baseline docs missing"})
        else:
            resolved_baseline = baseline_path if baseline_path else fallback_baselines[0]
            checked_assets.append({"project": name, "type": "baseline", "path": str(resolved_baseline.relative_to(overlay_root) if resolved_baseline.is_relative_to(overlay_root) else resolved_baseline)})
            asset_freshness(resolved_baseline, name, freshness_days, warnings)
    return {
        "schema": "codex-overlay-health-v1",
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "project_count": len(projects),
        "project_skill_count": project_skill_count,
        "skipped_skill_count": skipped_skill_count,
        "registry_sources": registry_sources,
        "freshness_days": freshness_days,
        "policy": {
            "project_skill_required_sections": sorted(normalized_policy["project_skill_required_sections"]),
            "block_on_missing_sections": sorted(normalized_policy["block_on_missing_sections"]),
        },
        "checked_assets": checked_assets,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check private overlay health")
    parser.add_argument("--overlay-root", required=True)
    parser.add_argument("--overlay-freshness-days", type=int, default=30)
    parser.add_argument("--policy", help="Optional overlay health policy YAML/JSON file")
    args = parser.parse_args()
    policy = load_json(Path(args.policy)) if args.policy and str(args.policy).endswith(".json") else load_yaml_like(Path(args.policy)) if args.policy else None
    result = check(Path(args.overlay_root), freshness_days=args.overlay_freshness_days, policy=policy)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
