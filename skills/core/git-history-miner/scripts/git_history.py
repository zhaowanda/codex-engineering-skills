#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA = "codex-git-history-mining-v1"


def run(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], text=True, capture_output=True, check=False)


def mine(repo: Path, project: str) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    log = run(repo, ["log", "--pretty=%h %s", "-n", "30"])
    if log.returncode != 0:
        warnings.append({"source": "git", "message": "repository has no readable git history"})
        return {"schema": SCHEMA, "project": project, "decision": "warn", "recent_commits": [], "hot_files": [], "hot_directories": [], "blockers": blockers, "warnings": warnings}
    recent = [line.strip() for line in log.stdout.splitlines() if line.strip()]
    files = run(repo, ["log", "--name-only", "--pretty=format:", "-n", "50"])
    file_counts = Counter(line.strip() for line in files.stdout.splitlines() if line.strip())
    dir_counts = Counter(Path(path).parts[0] for path in file_counts if Path(path).parts)
    return {
        "schema": SCHEMA,
        "project": project,
        "decision": "pass",
        "recent_commits": recent,
        "hot_files": [{"path": path, "count": count} for path, count in file_counts.most_common(30)],
        "hot_directories": [{"path": path, "count": count} for path, count in dir_counts.most_common(20)],
        "blockers": blockers,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine git history")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--project", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    result = mine(Path(args.repo), args.project)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
