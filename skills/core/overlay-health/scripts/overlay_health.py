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
    registry_path = overlay_root / "projects.yaml"
    registry = load_yaml_like(registry_path) if registry_path.exists() else {}
    projects = registry.get("projects", []) if isinstance(registry.get("projects"), list) else []
    if not registry_path.exists():
        blockers.append({"source": "projects.yaml", "message": "project registry is required"})
    for project in projects:
        if not isinstance(project, dict):
            continue
        name = str(project.get("name") or "")
        if not name:
            blockers.append({"source": "projects", "message": "project name is required"})
            continue
        skill_path = overlay_root / "skills" / name / "SKILL.md"
        if not skill_path.exists():
            blockers.append({"source": name, "message": "project skill missing"})
        else:
            check_project_skill_content(skill_path, name, blockers, warnings, normalized_policy)
        assets = project.get("assets") if isinstance(project.get("assets"), dict) else {}
        index_path = overlay_root / str(assets.get("index", f"indexes/{name}.code_index.json"))
        baseline_path = overlay_root / str(assets.get("baseline", f"baseline/{name}.baseline.json"))
        fallback_indexes = list((overlay_root / "indexes").glob(f"{name}*.json"))
        fallback_baselines = list((overlay_root / "baseline").glob(f"{name}*.json"))
        if not index_path.exists() and not fallback_indexes:
            blockers.append({"source": name, "message": "project index missing"})
        else:
            asset_freshness(index_path if index_path.exists() else fallback_indexes[0], name, freshness_days, warnings)
        if not baseline_path.exists() and not fallback_baselines:
            blockers.append({"source": name, "message": "baseline docs missing"})
        else:
            asset_freshness(baseline_path if baseline_path.exists() else fallback_baselines[0], name, freshness_days, warnings)
    return {
        "schema": "codex-overlay-health-v1",
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "project_count": len(projects),
        "freshness_days": freshness_days,
        "policy": {
            "project_skill_required_sections": sorted(normalized_policy["project_skill_required_sections"]),
            "block_on_missing_sections": sorted(normalized_policy["block_on_missing_sections"]),
        },
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
