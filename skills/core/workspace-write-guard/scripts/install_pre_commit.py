#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

WRITE_GUARD = Path(__file__).with_name("write_guard.py").resolve()
HARNESS = (Path(__file__).parents[2] / "auto-runner/scripts/harness_validation.py").resolve()
AGENT_RUNTIME = (Path(__file__).parents[2] / "auto-runner/scripts/agent_runtime.py").resolve()
HARNESS_POLICY = (Path(__file__).parents[4] / "config/harness-policy.example.yaml").resolve()


HOOK_TEMPLATE = """#!/usr/bin/env bash
set -euo pipefail

GUARD="${CODEX_WRITE_GUARD_SCRIPT:-__WRITE_GUARD__}"
REPO="$(git rev-parse --show-toplevel)"
PERMIT="${CODEX_EDIT_PERMIT:-}"
SNAPSHOT="${CODEX_WRITE_GUARD_SNAPSHOT:-}"
DOC_ID="${CODEX_DOC_ID:-}"

if [[ -z "$PERMIT" ]]; then
  echo "workspace-write-guard: CODEX_EDIT_PERMIT is required before commit" >&2
  exit 1
fi

python3 "$GUARD" hook-check \\
  --repo "$REPO" \\
  --permit "$PERMIT" \\
  ${SNAPSHOT:+--snapshot "$SNAPSHOT"} \\
  ${DOC_ID:+--doc-id "$DOC_ID"}
"""


PRE_PUSH_TEMPLATE = """#!/usr/bin/env bash
set -euo pipefail

HARNESS="${CODEX_HARNESS_SCRIPT:-__HARNESS__}"
RUNTIME="${CODEX_AGENT_RUNTIME_SCRIPT:-__AGENT_RUNTIME__}"
POLICY="${CODEX_HARNESS_POLICY:-__HARNESS_POLICY__}"
REPO="$(git rev-parse --show-toplevel)"
ARTIFACT_DIR="${CODEX_ARTIFACT_DIR:-}"

if [[ -z "$ARTIFACT_DIR" ]]; then
  echo "workflow-harness: CODEX_ARTIFACT_DIR is required before push" >&2
  exit 1
fi

python3 "$RUNTIME" advance \
  --artifact-dir "$ARTIFACT_DIR" \
  --name pre_push

python3 "$HARNESS" \
  --artifact-dir "$ARTIFACT_DIR" \
  --checkpoint pre_push \
  --policy "$POLICY" \
  --repo "$REPO" \
  --out "$ARTIFACT_DIR/harness/pre_push.json"
"""


def install(repo: Path, force: bool = False) -> dict[str, Any]:
    repo = repo.resolve()
    git_dir = repo / ".git"
    if not git_dir.exists():
        return {"repo": str(repo), "status": "skipped", "reason": "not a git repo"}
    targets = {
        "pre-commit": HOOK_TEMPLATE.replace("__WRITE_GUARD__", str(WRITE_GUARD)),
        "pre-push": PRE_PUSH_TEMPLATE.replace("__HARNESS__", str(HARNESS)).replace("__AGENT_RUNTIME__", str(AGENT_RUNTIME)).replace("__HARNESS_POLICY__", str(HARNESS_POLICY)),
    }
    installed: list[str] = []
    skipped: list[str] = []
    for name, content in targets.items():
        target = git_dir / "hooks" / name
        if target.exists() and not force:
            skipped.append(str(target))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        target.chmod(0o755)
        installed.append(str(target))
    status = "installed" if installed else "skipped"
    return {"repo": str(repo), "status": status, "installed": installed, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser(description="Install workspace write guard pre-commit and Harness pre-push hooks")
    parser.add_argument("--repo", action="append", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    results = [install(Path(repo), args.force) for repo in args.repo]
    print(json.dumps({"schema": "codex-write-guard-hook-install-v1", "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
