#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "codex-config-surface-v1"
SKIP = {".git", "node_modules", "dist", "build", "target", "__pycache__", ".venv", "venv"}
CONFIG_SUFFIXES = {".env", ".yaml", ".yml", ".toml", ".properties", ".ini"}
CONFIG_NAMES = {"Dockerfile", "docker-compose.yml", "docker-compose.yaml", ".gitlab-ci.yml", "Jenkinsfile"}
KEY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.-]{2,})\s*[:=]", re.M)


def iter_files(repo: Path):
    for path in repo.rglob("*"):
        if not path.is_file() or any(part in SKIP for part in path.parts):
            continue
        if path.suffix.lower() in CONFIG_SUFFIXES or path.name in CONFIG_NAMES or ".github/workflows" in path.as_posix():
            yield path


def extract(repo: Path, project: str) -> dict[str, Any]:
    if not repo.exists() or not repo.is_dir():
        return {
            "schema": SCHEMA,
            "project": project,
            "decision": "block",
            "confidence": "low",
            "confidence_details": [{"dimension": "repo", "score": 0, "reason": "repo path is missing or not a directory"}],
            "config_file_count": 0,
            "config_items": [],
            "blockers": [{"source": "repo", "message": "repo path is missing or not a directory"}],
            "warnings": [],
        }
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for path in iter_files(repo):
        text = path.read_text(encoding="utf-8", errors="ignore")
        keys = sorted(set(match.group(1) for match in KEY_RE.finditer(text)))[:100]
        items.append({"path": path.relative_to(repo).as_posix(), "type": path.suffix.lower() or path.name, "keys": keys})
    if not items:
        warnings.append({"source": "config_surface", "message": "no configuration files detected"})
    return {
        "schema": SCHEMA,
        "project": project,
        "decision": "block" if blockers else "warn" if warnings else "pass",
        "confidence": "high" if items else "low",
        "confidence_details": [
            {"dimension": "config_files", "score": min(100, len(items) * 25), "reason": f"{len(items)} configuration files detected"},
            {"dimension": "key_surface", "score": 100 if any(item.get("keys") for item in items) else 20 if items else 0, "reason": "configuration keys detected" if any(item.get("keys") for item in items) else "no configuration keys detected"},
        ],
        "config_file_count": len(items),
        "config_items": items,
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract configuration surface without values")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = extract(Path(args.repo), args.project)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
