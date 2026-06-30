#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


DIRS = ["human/specs", "human/designs", "human/releases", "machine/specs", "machine/designs", "machine/reviews", "machine/releases", "baseline", "indexes"]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def init(docs_root: Path, doc_id: str) -> dict[str, Any]:
    for directory in DIRS:
        (docs_root / directory).mkdir(parents=True, exist_ok=True)
    git_initialized = False
    if not is_git_repo(docs_root):
        proc = subprocess.run(["git", "init"], cwd=docs_root, text=True, capture_output=True)
        git_initialized = proc.returncode == 0
    manifest = {
        "schema": "codex-docs-governor-v1",
        "doc_id": doc_id,
        "docs_root": str(docs_root),
        "git_initialized": git_initialized,
        "human_docs": {
            "spec": f"human/specs/{doc_id}.md",
            "design": f"human/designs/{doc_id}.md",
            "release": f"human/releases/{doc_id}.md",
        },
        "machine_artifacts": {
            "spec": f"machine/specs/{doc_id}.spec.json",
            "design": f"machine/designs/{doc_id}.design.json",
            "review": f"machine/reviews/{doc_id}.review.json",
            "release": f"machine/releases/{doc_id}.release.json",
        },
        "rule": "Commit docs changes on a branch and merge through normal review; do not store local absolute paths or secrets.",
    }
    write_json(docs_root / "indexes" / f"{doc_id}.manifest.json", manifest)
    return manifest


def is_git_repo(path: Path) -> bool:
    proc = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path, text=True, capture_output=True)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def validate(docs_root: Path, doc_id: str, require_git: bool = False) -> dict[str, Any]:
    manifest_path = docs_root / "indexes" / f"{doc_id}.manifest.json"
    blockers: list[dict[str, str]] = []
    for directory in DIRS:
        if not (docs_root / directory).is_dir():
            blockers.append({"source": directory, "message": "required docs directory missing"})
    if not manifest_path.exists():
        blockers.append({"source": "manifest", "message": "doc manifest missing"})
    if require_git:
        if not docs_root.exists():
            blockers.append({"source": "docs_root", "message": "docs root missing"})
        elif not is_git_repo(docs_root):
            blockers.append({"source": "docs_git", "message": "docs root must be a git repository"})
    return {
        "schema": "codex-docs-governor-validation-v1",
        "decision": "block" if blockers else "pass",
        "blockers": blockers,
        "manifest": str(manifest_path),
        "git_required": require_git,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize or validate delivery docs structure")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for cmd in ["init", "validate"]:
        p = sub.add_parser(cmd)
        p.add_argument("--docs-root", required=True)
        p.add_argument("--doc-id", required=True)
        p.add_argument("--require-git", action="store_true")
    args = parser.parse_args()
    result = init(Path(args.docs_root), args.doc_id) if args.cmd == "init" else validate(Path(args.docs_root), args.doc_id, args.require_git)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("decision") != "block" else 1


if __name__ == "__main__":
    raise SystemExit(main())
