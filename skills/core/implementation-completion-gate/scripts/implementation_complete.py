#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def changed_files(diff: str) -> list[str]:
    files = []
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            if path != "/dev/null":
                files.append(path)
    return sorted(set(files))


def allowed_files(plan: dict[str, Any]) -> list[str]:
    allowed = []
    for task in plan.get("repo_tasks", []):
        if isinstance(task, dict):
            allowed.extend(str(item) for item in task.get("allowed_files", []) if item)
    return allowed


def evaluate(diff: str, plan: dict[str, Any], summary: str) -> dict[str, Any]:
    files = changed_files(diff)
    blockers: list[dict[str, Any]] = []
    allowed = allowed_files(plan)
    if not files:
        blockers.append({"source": "diff", "message": "no changed files detected"})
    if not summary.strip():
        blockers.append({"source": "summary", "message": "implementation summary is required"})
    if allowed:
        out_of_scope = [file for file in files if not any(file.startswith(prefix.strip("/")) or prefix.strip("/") in file for prefix in allowed)]
        if out_of_scope:
            blockers.append({"source": "scope", "message": "changed files outside delivery plan allowed_files", "files": out_of_scope})
    elif plan:
        blockers.append({"source": "delivery_plan", "message": "delivery plan has no allowed_files for scope check"})
    return {
        "schema": "codex-implementation-completion-v1",
        "decision": "block" if blockers else "pass",
        "changed_files": files,
        "implementation_summary": summary,
        "blockers": blockers,
        "warnings": [] if allowed else [{"source": "scope", "message": "scope check is weak without allowed_files"}],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate implementation completion")
    parser.add_argument("--diff-file", required=True)
    parser.add_argument("--delivery-plan", required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--out")
    args = parser.parse_args()
    result = evaluate(Path(args.diff_file).read_text(encoding="utf-8", errors="ignore"), load_json(Path(args.delivery_plan)), args.summary)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
