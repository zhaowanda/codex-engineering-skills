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
DEFAULT_INSTALLED_CATEGORY = "codex-engineering-skills"


def codex_skills_root() -> Path:
    return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "skills"


def discover_skills(root: Path, layer: str) -> dict[str, Path]:
    layer_root = root / "skills" / layer
    if not layer_root.exists():
        return {}
    return {path.parent.name: path.parent for path in sorted(layer_root.glob("*/SKILL.md"))}


def backup_path(skills_root: Path, category: str, name: str, stamp: str) -> Path:
    return skills_root / ".backup" / "codex-engineering-skills-sync" / stamp / category / name


def same_tree(path: Path, target: Path, mode: str) -> bool:
    if mode == "symlink":
        if not path.is_symlink():
            return False
        try:
            return path.resolve() == target.resolve()
        except OSError:
            return False
    marker = path / ".codex-engineering-skills-source"
    if not marker.exists():
        return False
    return marker.read_text(encoding="utf-8", errors="ignore").strip() == str(target.resolve())


def replace_skill(path: Path, target: Path, backup: Path, dry_run: bool, force: bool, mode: str) -> tuple[str, str | None]:
    if same_tree(path, target, mode) and not force:
        return "already_installed" if mode == "copy" else "already_linked", None
    if path.exists() or path.is_symlink():
        if not force:
            return "blocked", "destination exists; use --force to backup and replace"
        if not dry_run:
            backup.parent.mkdir(parents=True, exist_ok=True)
            if path.is_symlink():
                path.unlink()
            else:
                shutil.move(str(path), str(backup))
    if not dry_run and mode == "symlink":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.symlink_to(target, target_is_directory=True)
    if not dry_run and mode == "copy":
        shutil.copytree(target, path, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
        (path / ".codex-engineering-skills-source").write_text(str(target.resolve()) + "\n", encoding="utf-8")
    return "installed" if mode == "copy" else "linked", None


def sync(
    repo: Path,
    skills_root: Path,
    dry_run: bool,
    force: bool,
    mode: str = "copy",
    install_category: str = DEFAULT_INSTALLED_CATEGORY,
) -> dict[str, Any]:
    repo = repo.resolve()
    skills_root = skills_root.expanduser()
    core = discover_skills(repo, "core")
    templates = discover_skills(repo, "templates")
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    actions: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if mode not in {"copy", "symlink"}:
        blockers.append({"source": "mode", "message": "mode must be copy or symlink"})

    if not core:
        blockers.append({"source": str(repo / "skills/core"), "message": "no core skills found"})
    if blockers:
        return {"schema": SCHEMA, "decision": "block", "actions": actions, "blockers": blockers}

    installed_names: set[str] = set()
    for name, source in {**core, **templates}.items():
        if name in installed_names:
            blockers.append({"source": name, "message": "duplicate installed skill name"})
        installed_names.add(name)
    if blockers:
        return {"schema": SCHEMA, "decision": "block", "actions": actions, "blockers": blockers}

    for name, source in core.items():
        dest = skills_root / install_category / name
        category = install_category
        status, reason = replace_skill(dest, source, backup_path(skills_root, category, name, stamp), dry_run, force, mode)
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
        dest = skills_root / install_category / name
        status, reason = replace_skill(dest, source, backup_path(skills_root, install_category, name, stamp), dry_run, force, mode)
        action = {
            "skill": name,
            "layer": "templates",
            "category": install_category,
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
        "mode": mode,
        "force": force,
        "dry_run": dry_run,
        "action_count": len(actions),
        "installed_count": sum(1 for item in actions if item["status"] == "installed"),
        "linked_count": sum(1 for item in actions if item["status"] == "linked"),
        "already_installed_count": sum(1 for item in actions if item["status"] == "already_installed"),
        "already_linked_count": sum(1 for item in actions if item["status"] == "already_linked"),
        "blockers": blockers,
        "actions": actions,
        "install_note": f"Open-source skills are installed under {install_category}/. Use --prune-legacy to archive old local skill folders.",
    }


def prune_legacy(skills_root: Path, dry_run: bool, force: bool) -> dict[str, Any]:
    skills_root = skills_root.expanduser()
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    keep = {".system", ".backup", DEFAULT_INSTALLED_CATEGORY}
    actions: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    if not skills_root.exists():
        blockers.append({"source": display_path(skills_root), "message": "skills root does not exist"})
    else:
        for entry in sorted(skills_root.iterdir(), key=lambda item: item.name):
            if entry.name in keep:
                actions.append({"path": display_path(entry), "status": "kept"})
                continue
            target = skills_root / ".backup" / "codex-engineering-skills-prune" / stamp / entry.name
            if target.exists():
                blockers.append({"source": display_path(target), "message": "backup target already exists"})
                continue
            if not force:
                actions.append({"path": display_path(entry), "backup": display_path(target), "status": "would_archive"})
                continue
            if not dry_run:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(entry), str(target))
            actions.append({"path": display_path(entry), "backup": display_path(target), "status": "archived"})
    decision = "block" if blockers else "plan" if dry_run or not force else "pass"
    return {
        "schema": "codex-local-skill-prune-v1",
        "decision": decision,
        "skills_root": display_path(skills_root),
        "kept": sorted(keep),
        "action_count": len(actions),
        "blockers": blockers,
        "actions": actions,
    }


def display_path(path: Path) -> str:
    path = path.expanduser().absolute()
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except Exception:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Install local Codex skills from this open repository")
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--skills-root", default=str(codex_skills_root()))
    parser.add_argument("--mode", choices=["copy", "symlink"], default="copy")
    parser.add_argument("--install-category", default=DEFAULT_INSTALLED_CATEGORY)
    parser.add_argument("--prune-legacy", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.prune_legacy:
        result = prune_legacy(Path(args.skills_root), args.dry_run, args.force)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["decision"] != "block" else 1
    result = sync(
        Path(args.repo),
        Path(args.skills_root),
        args.dry_run,
        args.force,
        args.mode,
        args.install_category,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
