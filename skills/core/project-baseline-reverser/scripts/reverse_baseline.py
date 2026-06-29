#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


SKIP = {".git", "node_modules", "dist", "build", "target", "__pycache__", ".venv", "venv"}


def top_dirs(repo: Path) -> list[str]:
    result = []
    for path in repo.iterdir():
        if path.name in SKIP:
            continue
        if path.is_dir():
            result.append(path.name)
    return sorted(result)


def files_by_suffix(repo: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in repo.rglob("*"):
        if not path.is_file() or any(part in SKIP for part in path.parts):
            continue
        suffix = path.suffix.lower() or "[none]"
        counts[suffix] = counts.get(suffix, 0) + 1
    return dict(sorted(counts.items()))


def git_log(repo: Path) -> list[str]:
    try:
        proc = subprocess.run(["git", "-C", str(repo), "log", "--oneline", "-n", "20"], text=True, capture_output=True, check=False)
    except Exception:
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def reverse(repo: Path, project: str) -> dict[str, Any]:
    suffixes = files_by_suffix(repo)
    modules = [{"module": name, "reason": "top-level directory"} for name in top_dirs(repo)]
    tests = [path.relative_to(repo).as_posix() for path in repo.rglob("*test*") if path.is_file() and not any(part in SKIP for part in path.parts)][:50]
    configs = [path.relative_to(repo).as_posix() for path in repo.rglob("*") if path.is_file() and path.suffix.lower() in {".yaml", ".yml", ".toml", ".properties", ".env"} and not any(part in SKIP for part in path.parts)][:50]
    return {
        "schema": "codex-project-baseline-v1",
        "project": project,
        "repo_root": str(repo),
        "overview": f"{project} baseline inferred from repository structure, file types, tests, config files, and recent git history.",
        "top_level_directories": top_dirs(repo),
        "file_type_summary": suffixes,
        "module_hints": modules,
        "api_surface_ref": "api_surface.json",
        "config_surface_ref": "config_surface.json",
        "dependency_surface_ref": "dependency_surface.json",
        "test_hints": tests,
        "config_hints": configs,
        "risk_hints": ["Baseline is heuristic; verify module ownership, runtime behavior, API contracts, and configuration semantics with maintainers."],
        "recent_git_changes": git_log(repo),
        "human_followups": ["Confirm module boundaries.", "Confirm runtime entrypoints.", "Confirm critical configuration and deployment flow.", "Confirm test command coverage."],
        "limitations": ["Generated baseline is inferred from code and git history; owner review is required."],
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Reverse baseline docs from project source")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = reverse(Path(args.repo), args.project)
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
