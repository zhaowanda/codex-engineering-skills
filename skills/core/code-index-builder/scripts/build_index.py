#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


TEXT_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".vue", ".java", ".kt", ".go", ".rs", ".php", ".rb", ".cs", ".md", ".yaml", ".yml", ".json", ".toml"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", "target", "__pycache__", ".venv", "venv", ".idea", ".vscode"}
SYMBOL_PATTERNS = [
    re.compile(r"^\s*(def|class)\s+([A-Za-z_][A-Za-z0-9_]*)"),
    re.compile(r"^\s*(function|class|const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)"),
    re.compile(r"^\s*(public|private|protected)?\s*(class|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)"),
]
ROUTE_PATTERN = re.compile(r"(@(?:Get|Post|Put|Delete|Patch)?Mapping\s*\([^)]*\)|router\.(?:get|post|put|delete|patch)\s*\([^)]*|path\s*[:=]\s*['\"][^'\"]+)", re.I)


def iter_files(repo: Path):
    for path in repo.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def extract_symbols(text: str) -> list[str]:
    symbols: list[str] = []
    for line in text.splitlines():
        for pattern in SYMBOL_PATTERNS:
            match = pattern.search(line)
            if match:
                symbols.append(match.group(match.lastindex or 1))
    return symbols[:50]


def extract_routes(text: str) -> list[str]:
    return [match.group(0)[:160] for match in ROUTE_PATTERN.finditer(text)][:50]


def build(repo: Path, project: str) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in iter_files(repo):
        rel = path.relative_to(repo).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        files.append({
            "path": rel,
            "suffix": path.suffix.lower(),
            "line_count": len(text.splitlines()),
            "symbols": extract_symbols(text),
            "routes": extract_routes(text),
            "keywords": sorted(set(re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", text)))[:80],
        })
    return {
        "schema": "codex-code-index-v1",
        "project": project,
        "repo_root": str(repo),
        "file_count": len(files),
        "files": files,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build compact code index")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = build(Path(args.repo), args.project)
    write_json(Path(args.out), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
