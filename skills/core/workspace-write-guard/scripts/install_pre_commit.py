#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


WRITE_GUARD = Path(__file__).with_name("write_guard.py").resolve()


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


def install(repo: Path, force: bool = False) -> dict[str, str]:
    repo = repo.resolve()
    git_dir = repo / ".git"
    if not git_dir.exists():
        return {"repo": str(repo), "status": "skipped", "reason": "not a git repo"}
    target = git_dir / "hooks" / "pre-commit"
    if target.exists() and not force:
        return {"repo": str(repo), "status": "skipped", "reason": "pre-commit already exists"}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(HOOK_TEMPLATE.replace("__WRITE_GUARD__", str(WRITE_GUARD)), encoding="utf-8")
    target.chmod(0o755)
    return {"repo": str(repo), "status": "installed", "target": str(target)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Install workspace write guard pre-commit hook")
    parser.add_argument("--repo", action="append", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    results = [install(Path(repo), args.force) for repo in args.repo]
    print(json.dumps({"schema": "codex-write-guard-hook-install-v1", "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
