#!/usr/bin/env python3
from __future__ import annotations

import argparse
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


def check(overlay_root: Path) -> dict[str, Any]:
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
        if not (overlay_root / "skills" / name / "SKILL.md").exists():
            blockers.append({"source": name, "message": "project skill missing"})
        assets = project.get("assets") if isinstance(project.get("assets"), dict) else {}
        index_path = overlay_root / str(assets.get("index", f"indexes/{name}.code_index.json"))
        baseline_path = overlay_root / str(assets.get("baseline", f"baseline/{name}.baseline.json"))
        if not index_path.exists() and not list((overlay_root / "indexes").glob(f"{name}*.json")):
            warnings.append({"source": name, "message": "project index missing"})
        if not baseline_path.exists() and not list((overlay_root / "baseline").glob(f"{name}*.json")):
            warnings.append({"source": name, "message": "baseline docs missing"})
    return {
        "schema": "codex-overlay-health-v1",
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "project_count": len(projects),
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check private overlay health")
    parser.add_argument("--overlay-root", required=True)
    args = parser.parse_args()
    result = check(Path(args.overlay_root))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
