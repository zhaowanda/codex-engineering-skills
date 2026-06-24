#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def skill_md(project: str, project_type: str) -> str:
    return f"""---
name: {project}
description: Project-specific overlay skill for {project}. Use when a requirement is routed to this {project_type} repository; keep private boundaries, indexes, baseline docs, and business semantics in the private overlay.
---

# {project}

Use this private project skill only after the requirement is routed to this repository.

## Required Private References

- project registry entry
- compact code index
- baseline docs
- project-specific validation commands

Do not copy private details into the open-core repository.
"""


def onboard(project: str, repo: str, project_type: str, overlay_root: Path, default_branch: str) -> dict[str, Any]:
    skill_dir = overlay_root / "skills" / project
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(skill_md(project, project_type), encoding="utf-8")
    registry_entry = {
        "name": project,
        "root": repo,
        "type": project_type,
        "default_branch": default_branch,
        "skill": project,
        "roles": [project_type],
        "related_projects": [],
        "test_strategy": "",
    }
    manifest = {
        "schema": "codex-project-onboard-v1",
        "project": project,
        "skill_path": str(skill_dir / "SKILL.md"),
        "registry_entry": registry_entry,
        "next_action": "Add registry_entry to private projects.yaml and build a private code index.",
    }
    out = overlay_root / "onboarding" / f"{project}.onboard.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Onboard project into private overlay")
    parser.add_argument("--project", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--type", required=True)
    parser.add_argument("--overlay-root", required=True)
    parser.add_argument("--default-branch", default="main")
    args = parser.parse_args()
    result = onboard(args.project, args.repo, args.type, Path(args.overlay_root), args.default_branch)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
