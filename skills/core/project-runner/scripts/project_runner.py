#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-project-runner-summary-v1"
HERE = Path(__file__).resolve()


def skill_script(skill: str, script: str) -> Path:
    candidates = [
        HERE.parents[4] / "skills/core" / skill / "scripts" / script,
        HERE.parents[2].parent / skill / "scripts" / script,
        HERE.parents[2] / skill / "scripts" / script,
        HERE.parents[2].parent / "open-core" / skill / "scripts" / script,
        HERE.parents[2].parent / "company" / skill / "scripts" / script,
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"cannot locate installed skill script: {skill}/scripts/{script}")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


project_onboard = load_module("project_onboard", skill_script("project-onboard", "project_onboard.py"))
code_index = load_module("code_index", skill_script("code-index-builder", "build_index.py"))
overlay_health = load_module("overlay_health", skill_script("overlay-health", "overlay_health.py"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_canonical_index(repo: Path, project: str, overlay_root: Path) -> Path:
    index = code_index.build(repo, project)
    index_path = overlay_root / "indexes" / f"{project}.code_index.json"
    write_json(index_path, index)
    return index_path


def summarize(
    mode: str,
    project: str,
    overlay_root: Path,
    onboard_result: dict[str, Any],
    index_path: Path,
    understanding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    health = overlay_health.check(overlay_root)
    blockers: list[dict[str, Any]] = []
    if health.get("decision") == "block":
        blockers.extend(health.get("blockers", []))
    if understanding and understanding.get("decision") == "block":
        blockers.extend(understanding.get("blockers", []))
    baseline_path = onboard_result.get("baseline_path")
    summary = {
        "schema": SCHEMA,
        "decision": "block" if blockers else "warn" if health.get("decision") == "warn" else "pass",
        "mode": mode,
        "project": project,
        "overlay_root": str(overlay_root),
        "skill_path": onboard_result.get("skill_path"),
        "reference_dir": onboard_result.get("reference_dir"),
        "registry_path": onboard_result.get("registry_path"),
        "index_path": str(index_path),
        "baseline_path": baseline_path,
        "project_understanding": understanding,
        "overlay_health": health,
        "blockers": blockers,
        "next_actions": [
            "Review generated project references before using them as authoritative project knowledge.",
            "Use code-index-lookup against the canonical index before broad source reads.",
            "Run auto-runner with --repo and --project for requirement delivery work.",
        ],
    }
    out = overlay_root / "onboarding" / f"{project}.{mode}.summary.json"
    write_json(out, summary)
    summary["summary_path"] = str(out)
    return summary


def run_new(
    project: str,
    repo: Path,
    project_type: str,
    overlay_root: Path,
    default_branch: str,
    git_url: str | None = None,
    dependencies: list[str] | None = None,
) -> dict[str, Any]:
    onboard_result = project_onboard.onboard(
        project,
        str(repo),
        project_type,
        overlay_root,
        default_branch,
        mode="new",
        git_url=git_url,
        dependencies=dependencies,
    )
    index_path = build_canonical_index(repo, project, overlay_root)
    return summarize("new", project, overlay_root, onboard_result, index_path)


def run_legacy(
    project: str,
    repo: Path,
    project_type: str,
    overlay_root: Path,
    default_branch: str,
    out: Path,
    git_url: str | None = None,
    dependencies: list[str] | None = None,
) -> dict[str, Any]:
    project_understand = load_module("project_understand", skill_script("project-understanding-runner", "project_understand.py"))
    understanding = project_understand.run(
        repo,
        project,
        out,
        overlay_root=overlay_root,
        project_type=project_type,
        default_branch=default_branch,
        write_project_skill=True,
        git_url=git_url,
        dependencies=dependencies,
    )
    project_skill = understanding.get("project_skill", {})
    index_path = overlay_root / "indexes" / f"{project}.code_index.json"
    if not index_path.exists():
        index_path = build_canonical_index(repo, project, overlay_root)
    return summarize("legacy", project, overlay_root, project_skill, index_path, understanding=understanding)


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified project setup runner")
    sub = parser.add_subparsers(dest="mode", required=True)
    for name in ["new", "legacy"]:
        mode_parser = sub.add_parser(name)
        mode_parser.add_argument("--project", required=True)
        mode_parser.add_argument("--repo", required=True)
        mode_parser.add_argument("--type", required=True)
        mode_parser.add_argument("--overlay-root", required=True)
        mode_parser.add_argument("--default-branch", default="main")
        mode_parser.add_argument("--git-url")
        mode_parser.add_argument("--depends-on", action="append", default=[])
        if name == "legacy":
            mode_parser.add_argument("--out")
    args = parser.parse_args()
    overlay_root = Path(args.overlay_root)
    repo = Path(args.repo)
    if args.mode == "new":
        result = run_new(
            args.project,
            repo,
            args.type,
            overlay_root,
            args.default_branch,
            git_url=args.git_url,
            dependencies=args.depends_on,
        )
    else:
        out = Path(args.out) if args.out else overlay_root / "baseline" / f"{args.project}.understanding"
        result = run_legacy(
            args.project,
            repo,
            args.type,
            overlay_root,
            args.default_branch,
            out,
            git_url=args.git_url,
            dependencies=args.depends_on,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
