#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA = "codex-local-skill-sync-v1"
DEFAULT_OVERLAY_CATEGORY = "company"
DEFAULT_OPEN_CATEGORY = "open-core"
DEFAULT_TEMPLATE_CATEGORY = "open-core-templates"


def codex_skills_root() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills"


def discover_skills(root: Path, layer: str) -> dict[str, Path]:
    layer_root = root / "skills" / layer
    if not layer_root.exists():
        return {}
    return {path.parent.name: path.parent for path in sorted(layer_root.glob("*/SKILL.md"))}


def backup_path(skills_root: Path, category: str, name: str, stamp: str) -> Path:
    return skills_root / ".backup" / "codex-engineering-skills-sync" / stamp / category / name


def same_symlink(path: Path, target: Path) -> bool:
    if not path.is_symlink():
        return False
    try:
        return path.resolve() == target.resolve()
    except OSError:
        return False


def replace_with_symlink(path: Path, target: Path, backup: Path, dry_run: bool, force: bool) -> tuple[str, str | None]:
    if same_symlink(path, target):
        return "already_linked", None
    if path.exists() or path.is_symlink():
        if not force:
            return "blocked", "destination exists; use --force to backup and replace"
        if not dry_run:
            backup.parent.mkdir(parents=True, exist_ok=True)
            if path.is_symlink():
                path.unlink()
            else:
                shutil.move(str(path), str(backup))
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target, target_is_directory=True)
    return "linked", None


def sync(
    repo: Path,
    skills_root: Path,
    dry_run: bool,
    force: bool,
    overlay_category: str = DEFAULT_OVERLAY_CATEGORY,
    open_category: str = DEFAULT_OPEN_CATEGORY,
    template_category: str = DEFAULT_TEMPLATE_CATEGORY,
) -> dict[str, Any]:
    repo = repo.resolve()
    skills_root = skills_root.expanduser()
    core = discover_skills(repo, "core")
    templates = discover_skills(repo, "templates")
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    actions: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []

    if not core:
        blockers.append({"source": str(repo / "skills/core"), "message": "no core skills found"})
    if blockers:
        return {"schema": SCHEMA, "decision": "block", "actions": actions, "blockers": blockers}

    overlay_root = skills_root / overlay_category
    existing_overlay = {path.name for path in overlay_root.iterdir()} if overlay_root.exists() else set()
    for name, source in core.items():
        if name in existing_overlay:
            dest = overlay_root / name
            category = overlay_category
        else:
            dest = skills_root / open_category / name
            category = open_category
        status, reason = replace_with_symlink(dest, source, backup_path(skills_root, category, name, stamp), dry_run, force)
        action = {
            "skill": name,
            "layer": "core",
            "category": category,
            "destination": display_path(dest),
            "source": str(source.relative_to(repo)),
            "status": status,
        }
        if reason:
            action["reason"] = reason
            blockers.append({"source": display_path(dest), "message": reason})
        actions.append(action)

    for name, source in templates.items():
        dest = skills_root / template_category / name
        status, reason = replace_with_symlink(dest, source, backup_path(skills_root, template_category, name, stamp), dry_run, force)
        action = {
            "skill": name,
            "layer": "templates",
            "category": template_category,
            "destination": display_path(dest),
            "source": str(source.relative_to(repo)),
            "status": status,
        }
        if reason:
            action["reason"] = reason
            blockers.append({"source": display_path(dest), "message": reason})
        actions.append(action)

    decision = "block" if blockers else "plan" if dry_run else "pass"
    return {
        "schema": SCHEMA,
        "decision": decision,
        "skills_root": display_path(skills_root),
        "repo": str(repo),
        "mode": "symlink",
        "force": force,
        "dry_run": dry_run,
        "action_count": len(actions),
        "linked_count": sum(1 for item in actions if item["status"] == "linked"),
        "already_linked_count": sum(1 for item in actions if item["status"] == "already_linked"),
        "blockers": blockers,
        "actions": actions,
        "private_overlay_note": f"Non-overlapping private skills under {overlay_category}/ are left untouched.",
    }


def display_path(path: Path) -> str:
    path = path.expanduser().absolute()
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except Exception:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync local Codex skills to this open repository as the maintenance source")
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--skills-root", default=str(codex_skills_root()))
    parser.add_argument("--overlay-category", default=DEFAULT_OVERLAY_CATEGORY)
    parser.add_argument("--open-category", default=DEFAULT_OPEN_CATEGORY)
    parser.add_argument("--template-category", default=DEFAULT_TEMPLATE_CATEGORY)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = sync(
        Path(args.repo),
        Path(args.skills_root),
        args.dry_run,
        args.force,
        args.overlay_category,
        args.open_category,
        args.template_category,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
