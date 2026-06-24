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


def run(repo: Path, project: str, out: Path) -> dict[str, Any]:
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
    blockers = []
    if quality.get("decision") == "block":
        blockers.append({"source": "baseline_quality", "message": "baseline quality blocked"})
    return {
        "schema": SCHEMA,
        "decision": "block" if blockers else "pass",
        "project": project,
        "repo": repo.name,
        "out": str(out),
        "generated_files": generated,
        "baseline_quality_decision": quality.get("decision"),
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run full project understanding pipeline")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = run(Path(args.repo), args.project, Path(args.out))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
