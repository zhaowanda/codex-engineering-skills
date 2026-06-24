#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-api-surface-v1"
SKIP = {".git", "node_modules", "dist", "build", "target", "__pycache__", ".venv", "venv"}
TEXT_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".vue"}
PATTERNS = {
    "fastapi": re.compile(r"@\w+\.(get|post|put|delete|patch)\(['\"]([^'\"]+)['\"]", re.I),
    "express": re.compile(r"(?:app|router)\.(get|post|put|delete|patch)\(['\"]([^'\"]+)['\"]", re.I),
    "spring": re.compile(r"@(Get|Post|Put|Delete|Patch|Request)?Mapping\s*\(([^)]*)\)", re.I),
    "frontend-route": re.compile(r"path\s*:\s*['\"]([^'\"]+)['\"]", re.I),
}


def iter_files(repo: Path):
    for path in repo.rglob("*"):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES and not any(part in SKIP for part in path.parts):
            yield path


def extract(repo: Path, project: str) -> dict[str, Any]:
    routes: list[dict[str, Any]] = []
    for path in iter_files(repo):
        text = path.read_text(encoding="utf-8", errors="ignore")
        rel = path.relative_to(repo).as_posix()
        for kind, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                route = match.group(2) if kind in {"fastapi", "express"} else match.group(1) if kind == "frontend-route" else match.group(0)
                method = match.group(1).upper() if kind in {"fastapi", "express"} else ""
                routes.append({"kind": kind, "method": method, "route": route[:180], "file": rel})
    return {"schema": SCHEMA, "project": project, "route_count": len(routes), "routes": routes[:500]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract API surface hints")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = extract(Path(args.repo), args.project)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
