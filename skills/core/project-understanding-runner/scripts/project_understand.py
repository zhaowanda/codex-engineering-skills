#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-project-understanding-run-v1"
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


repository_analyzer = load_module("repository_analyzer", skill_script("repository-analyzer", "repository_analyzer.py"))
api_surface = load_module("api_surface", skill_script("api-surface-extractor", "api_surface.py"))
config_surface = load_module("config_surface", skill_script("config-surface-extractor", "config_surface.py"))
dependency_surface = load_module("dependency_surface", skill_script("dependency-surface-analyzer", "dependency_surface.py"))
git_history = load_module("git_history", skill_script("git-history-miner", "git_history.py"))
code_index = load_module("code_index", skill_script("code-index-builder", "build_index.py"))
baseline = load_module("baseline", skill_script("project-baseline-reverser", "reverse_baseline.py"))
baseline_quality = load_module("baseline_quality", skill_script("baseline-quality-governor", "baseline_quality.py"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_human_baseline(path: Path, project: str, artifacts: dict[str, dict[str, Any]]) -> None:
    repo = artifacts["repository_analysis"]
    api = artifacts["api_surface"]
    config = artifacts["config_surface"]
    deps = artifacts["dependency_surface"]
    history = artifacts["git_history"]
    base = artifacts["baseline"]
    lines = [
        f"# {project} Baseline",
        "",
        "## Overview",
        str(base.get("overview", "")),
        "",
        "## Repository",
        f"- Languages: {', '.join(repo.get('languages', {}).keys()) or 'unknown'}",
        f"- Framework hints: {', '.join(repo.get('framework_hints', [])) or 'none'}",
        f"- Entry points: {', '.join(repo.get('entrypoint_hints', [])) or 'none'}",
        "",
        "## Modules",
        *[f"- {item.get('module')}: {item.get('reason')}" for item in base.get("module_hints", [])],
        "",
        "## API Surface",
        *[f"- {item.get('method', '')} {item.get('route')} ({item.get('file')})".strip() for item in api.get("routes", [])[:20]],
        "",
        "## Configuration Surface",
        *[f"- {item.get('path')}: {', '.join(item.get('keys', []))}" for item in config.get("config_items", [])[:20]],
        "",
        "## Dependencies",
        f"- Ecosystems: {', '.join(deps.get('ecosystems', [])) or 'unknown'}",
        f"- Test hints: {', '.join(deps.get('test_command_hints', [])) or 'none'}",
        "",
        "## Git History",
        *[f"- {item}" for item in history.get("recent_commits", [])[:10]],
        "",
        "## Risks And Follow-ups",
        *[f"- {item}" for item in base.get("risk_hints", []) + base.get("human_followups", [])],
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def enrich_project_skill(
    skill_dir: Path,
    artifacts: dict[str, dict[str, Any]],
    index_path: Path | None = None,
    baseline_path: Path | None = None,
) -> None:
    references = skill_dir / "references"
    if not references.exists():
        return

    base = artifacts["baseline"]
    api = artifacts["api_surface"]
    deps = artifacts["dependency_surface"]
    config = artifacts["config_surface"]
    code = artifacts["code_index"]

    feature_rows = [
        "| Feature | Owner Module | Entry Points | Notes |",
        "|---|---|---|---|",
    ]
    for item in base.get("module_hints", [])[:20]:
        feature_rows.append(
            f"| {item.get('module', 'unknown')} | {item.get('module', 'unknown')} | To be filled | {item.get('reason', '')} |"
        )
    if len(feature_rows) == 2:
        feature_rows.append("| To be filled | To be filled | To be filled | No module hints detected |")
    (references / "feature-map.md").write_text(
        "# Feature Map\n\n## Features\n\n" + "\n".join(feature_rows) + "\n\n## Routing Rules\n\n"
        "- Use this file to map requirements to modules before broad source reads.\n"
        "- Prefer code-index.md for file-level lookup hints.\n",
        encoding="utf-8",
    )

    api_rows = [
        "| Method | Route / Contract | File | Producer | Consumer | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for item in api.get("routes", [])[:50]:
        api_rows.append(
            f"| {item.get('method', '')} | {item.get('route', '')} | {item.get('file', '')} | This project | To be filled | heuristic |"
        )
    if len(api_rows) == 2:
        api_rows.append("| To be filled | No routes detected | To be filled | To be filled | To be filled | heuristic |")
    (references / "api-map.md").write_text(
        "# API Map\n\n## API / Route Surface\n\n" + "\n".join(api_rows) + "\n\n## Rules\n\n"
        "- Record endpoint and contract hints only.\n"
        "- Do not store real tokens, payloads with customer data, or private hostnames.\n",
        encoding="utf-8",
    )

    files = [item.get("path", "") for item in code.get("files", [])[:30] if item.get("path")]
    modules = [item.get("module", "") for item in base.get("module_hints", [])[:20] if item.get("module")]
    index_lines = [
        "# Code Index",
        "",
        "## Index Location",
        "",
        f"- Canonical index: {index_path.as_posix() if index_path else 'indexes/<project>.code_index.json'}",
        "- Lookup protocol: use code-index-lookup before broad source reads.",
        "",
        "## Read-First Hints",
        "",
        *[f"- `{path}`" for path in files],
        "",
        "## Module Hints",
        "",
        *[f"- `{module}`" for module in modules],
        "",
        "## Generated Artifacts",
        "",
        f"- {index_path.as_posix() if index_path else 'code_index.json'}: private generated index from code-index-builder.",
        f"- {baseline_path.as_posix() if baseline_path else 'baseline.json'}: private generated baseline from project-baseline-reverser.",
        "",
        "## Expert Search Protocol",
        "",
        "- Search the canonical index for symbols, routes, pages, services, and business keywords first.",
        "- Use targeted source reads after index lookup; avoid broad repository scans unless lookup is insufficient.",
        "- Refresh the canonical index after navigation-relevant changes.",
    ]
    (references / "code-index.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")

    commands = deps.get("test_command_hints", [])
    ecosystems = deps.get("ecosystems", [])
    config_paths = [item.get("path", "") for item in config.get("config_items", [])[:20] if item.get("path")]
    validation_lines = [
        "# Validation Recipes",
        "",
        "## Commands",
        "",
        f"- Build: To be filled ({', '.join(ecosystems) or 'unknown ecosystem'})",
        f"- Test: {', '.join(commands) if commands else 'To be filled'}",
        "- Lint: To be filled",
        "- Type check: To be filled",
        "",
        "## Configuration Watch List",
        "",
        *[f"- `{path}`" for path in config_paths],
        "",
        "## Evidence Rules",
        "",
        "- Capture command, exit code, and relevant output.",
        "- Link browser or API evidence when user-visible behavior changes.",
    ]
    (references / "validation-recipes.md").write_text("\n".join(validation_lines) + "\n", encoding="utf-8")


def run(
    repo: Path,
    project: str,
    out: Path,
    overlay_root: Path | None = None,
    project_type: str = "generic",
    default_branch: str = "main",
    write_project_skill: bool = False,
    git_url: str | None = None,
    dependencies: list[str] | None = None,
) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, dict[str, Any]] = {
        "repository_analysis": repository_analyzer.analyze(repo, project),
        "api_surface": api_surface.extract(repo, project),
        "config_surface": config_surface.extract(repo, project),
        "dependency_surface": dependency_surface.analyze(repo, project),
        "git_history": git_history.mine(repo, project),
        "code_index": code_index.build(repo, project),
        "baseline": baseline.reverse(repo, project),
    }
    files = {
        "repository_analysis": out / "repository_analysis.json",
        "api_surface": out / "api_surface.json",
        "config_surface": out / "config_surface.json",
        "dependency_surface": out / "dependency_surface.json",
        "git_history": out / "git_history.json",
        "code_index": out / "code_index.json",
        "baseline": out / "baseline.json",
    }
    for name, path in files.items():
        write_json(path, artifacts[name])
    quality = baseline_quality.review(files["baseline"])
    artifacts["baseline_quality"] = quality
    write_json(out / "baseline_quality.json", quality)
    write_human_baseline(out / "human_baseline.md", project, artifacts)
    generated = [path.name for path in files.values()] + ["baseline_quality.json", "human_baseline.md"]
    project_skill: dict[str, Any] | None = None
    if write_project_skill:
        if overlay_root is None:
            overlay_root = out
        project_onboard = load_module("project_onboard", skill_script("project-onboard", "project_onboard.py"))
        project_skill = project_onboard.onboard(
            project,
            str(repo),
            project_type,
            overlay_root,
            default_branch,
            mode="legacy",
            git_url=git_url,
            dependencies=dependencies,
        )
        overlay_index = overlay_root / "indexes" / f"{project}.code_index.json"
        overlay_baseline = overlay_root / "baseline" / f"{project}.baseline.json"
        write_json(overlay_index, artifacts["code_index"])
        write_json(overlay_baseline, artifacts["baseline"])
        enrich_project_skill(
            Path(project_skill["skill_path"]).parent,
            artifacts,
            index_path=Path("indexes") / f"{project}.code_index.json",
            baseline_path=Path("baseline") / f"{project}.baseline.json",
        )
        generated.append("project_skill")
        generated.extend([str(overlay_index), str(overlay_baseline)])
    blockers = []
    if quality.get("decision") == "block":
        blockers.append({"source": "baseline_quality", "message": "baseline quality blocked"})
    result = {
        "schema": SCHEMA,
        "decision": "block" if blockers else "pass",
        "project": project,
        "repo": repo.name,
        "out": str(out),
        "generated_files": generated,
        "baseline_quality_decision": quality.get("decision"),
        "blockers": blockers,
    }
    if project_skill is not None:
        result["project_skill"] = project_skill
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full project understanding pipeline")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--overlay-root")
    parser.add_argument("--type", default="generic")
    parser.add_argument("--default-branch", default="main")
    parser.add_argument("--write-project-skill", action="store_true")
    parser.add_argument("--git-url")
    parser.add_argument("--depends-on", action="append", default=[])
    args = parser.parse_args()
    result = run(
        Path(args.repo),
        args.project,
        Path(args.out),
        overlay_root=Path(args.overlay_root) if args.overlay_root else None,
        project_type=args.type,
        default_branch=args.default_branch,
        write_project_skill=args.write_project_skill,
        git_url=args.git_url,
        dependencies=args.depends_on,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
