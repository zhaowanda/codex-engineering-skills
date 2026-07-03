#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "codex-repository-analysis-v1"
SKIP = {".git", "node_modules", "dist", "build", "target", "__pycache__", ".venv", "venv"}
LANG_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".vue": "vue",
}
BUILD_FILES = {"pyproject.toml", "requirements.txt", "package.json", "pom.xml", "build.gradle", "go.mod", "Cargo.toml"}
CI_HINTS = {".github/workflows", ".gitlab-ci.yml", "Jenkinsfile"}


def iter_files(repo: Path):
    for path in repo.rglob("*"):
        if path.is_file() and not any(part in SKIP for part in path.parts):
            yield path


def analyze(repo: Path, project: str) -> dict[str, Any]:
    if not repo.exists() or not repo.is_dir():
        return {
            "schema": SCHEMA,
            "project": project,
            "repo_root": str(repo),
            "decision": "block",
            "confidence": "low",
            "confidence_details": [{"dimension": "repo", "score": 0, "reason": "repo path is missing or not a directory"}],
            "file_count": 0,
            "languages": {},
            "suffix_counts": {},
            "top_level_directories": [],
            "framework_hints": [],
            "entrypoint_hints": [],
            "build_files": [],
            "config_files": [],
            "test_hints": [],
            "ci_files": [],
            "blockers": [{"source": "repo", "message": "repo path is missing or not a directory"}],
            "warnings": [],
        }
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    suffix_counts: dict[str, int] = {}
    languages: dict[str, int] = {}
    files = list(iter_files(repo))
    for path in files:
        suffix = path.suffix.lower()
        suffix_counts[suffix or "[none]"] = suffix_counts.get(suffix or "[none]", 0) + 1
        lang = LANG_BY_SUFFIX.get(suffix)
        if lang:
            languages[lang] = languages.get(lang, 0) + 1
    top_dirs = sorted(path.name for path in repo.iterdir() if path.is_dir() and path.name not in SKIP)
    build_files = sorted(path.relative_to(repo).as_posix() for path in files if path.name in BUILD_FILES)
    config_files = sorted(path.relative_to(repo).as_posix() for path in files if path.suffix.lower() in {".env", ".yaml", ".yml", ".toml", ".properties"})
    test_hints = sorted(path.relative_to(repo).as_posix() for path in files if "test" in path.name.lower() or "tests" in path.parts)
    ci_files = []
    for hint in CI_HINTS:
        target = repo / hint
        if target.exists():
            if target.is_dir():
                ci_files.extend(path.relative_to(repo).as_posix() for path in target.rglob("*") if path.is_file())
            else:
                ci_files.append(target.relative_to(repo).as_posix())
    entrypoint_hints = sorted(path.relative_to(repo).as_posix() for path in files if path.name in {"main.py", "app.py", "server.js", "index.js", "main.ts", "Application.java"})
    framework_hints = []
    text_names = " ".join(path.name.lower() for path in files)
    if "fastapi" in text_names or any("fastapi" in path.read_text(encoding="utf-8", errors="ignore").lower() for path in files if path.suffix == ".py"):
        framework_hints.append("fastapi")
    if "package.json" in text_names:
        framework_hints.append("node")
    if "pom.xml" in text_names:
        framework_hints.append("maven")
    if not files:
        warnings.append({"source": "repo", "message": "no readable files found"})
    elif not languages:
        warnings.append({"source": "languages", "message": "no known implementation language detected"})
    confidence = "high" if languages and build_files else "medium" if files else "low"
    return {
        "schema": SCHEMA,
        "project": project,
        "repo_root": repo.name,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "confidence": confidence,
        "confidence_details": [
            {"dimension": "files", "score": min(100, len(files)), "reason": f"{len(files)} files scanned"},
            {"dimension": "languages", "score": 100 if languages else 0, "reason": "known implementation language detected" if languages else "no known implementation language detected"},
            {"dimension": "build", "score": 100 if build_files else 0, "reason": "build manifest detected" if build_files else "no build manifest detected"},
            {"dimension": "tests", "score": 100 if test_hints else 20, "reason": "test files detected" if test_hints else "no test files detected"},
            {"dimension": "ci", "score": 100 if ci_files else 20, "reason": "CI config detected" if ci_files else "no CI config detected"},
        ],
        "file_count": len(files),
        "languages": dict(sorted(languages.items())),
        "suffix_counts": dict(sorted(suffix_counts.items())),
        "top_level_directories": top_dirs,
        "framework_hints": sorted(set(framework_hints)),
        "entrypoint_hints": entrypoint_hints,
        "build_files": build_files,
        "config_files": config_files,
        "test_hints": test_hints[:100],
        "ci_files": sorted(ci_files),
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze repository structure")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = analyze(Path(args.repo), args.project)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
