#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # nosec B404
from datetime import datetime, timezone
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

if [[ ! -f "$RUNTIME" ]]; then
  echo "workflow-harness: Agent Runtime script not found: $RUNTIME" >&2
  echo "workflow-harness: reinstall skills and repair this hook with workspace-write-guard/scripts/install_pre_commit.py --hook pre-push --force" >&2
  exit 1
fi

if [[ ! -f "$HARNESS" ]]; then
  echo "workflow-harness: Harness script not found: $HARNESS" >&2
  echo "workflow-harness: reinstall skills and repair this hook with workspace-write-guard/scripts/install_pre_commit.py --hook pre-push --force" >&2
  exit 1
fi

python3 "$RUNTIME" advance \
  --artifact-dir "$ARTIFACT_DIR" \
  --name pre_push

HARNESS_ARGS=(
  --artifact-dir "$ARTIFACT_DIR"
  --checkpoint pre_push
  --repo "$REPO"
  --out "$ARTIFACT_DIR/harness/pre_push.json"
)
if [[ -n "$POLICY" && -f "$POLICY" ]]; then
  HARNESS_ARGS+=(--policy "$POLICY")
fi
python3 "$HARNESS" "${HARNESS_ARGS[@]}"
"""


def git_dir_for(repo: Path) -> Path | None:
    git = shutil.which("git")
    if not git:
        return None
    proc = subprocess.run(
        [git, "rev-parse", "--absolute-git-dir"],  # nosec B603
        cwd=repo,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return Path(proc.stdout.strip()).resolve()


def dependency_blockers(hook_names: set[str]) -> list[dict[str, str]]:
    required = {"pre-commit": [WRITE_GUARD], "pre-push": [HARNESS, AGENT_RUNTIME]}
    return [
        {"source": name, "message": f"required hook dependency does not exist: {path}"}
        for name in sorted(hook_names)
        for path in required[name]
        if not path.is_file()
    ]


def managed_broken_hook(path: Path) -> bool:
    if not path.is_file():
        return False
    content = path.read_text(encoding="utf-8", errors="ignore")
    if not any(marker in content for marker in ["post-change-skill-sync/scripts/pre-push", "workflow-harness:", "workspace-write-guard:"]):
        return False
    references = re.findall(r"(?:exec\s+|HARNESS=|RUNTIME=|GUARD=)[\"']?([^\"'\s]+)", content)
    absolute_references = [Path(reference) for reference in references if reference.startswith("/")]
    return any(not reference.exists() for reference in absolute_references)


def backup_hook(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.codex-backup.{stamp}")
    counter = 1
    while backup.exists():
        backup = path.with_name(f"{path.name}.codex-backup.{stamp}.{counter}")
        counter += 1
    path.replace(backup)
    return backup


def install(repo: Path, force: bool = False, hook_names: set[str] | None = None) -> dict[str, Any]:
    repo = repo.resolve()
    selected = hook_names or {"pre-commit", "pre-push"}
    invalid = selected - {"pre-commit", "pre-push"}
    if invalid:
        return {"repo": str(repo), "status": "blocked", "blockers": [{"source": "hook", "message": f"unsupported hooks: {sorted(invalid)}"}]}
    git_dir = git_dir_for(repo)
    if git_dir is None:
        return {"repo": str(repo), "status": "skipped", "reason": "not a git repo"}
    blockers = dependency_blockers(selected)
    if blockers:
        return {"repo": str(repo), "status": "blocked", "blockers": blockers}
    targets = {
        "pre-commit": HOOK_TEMPLATE.replace("__WRITE_GUARD__", str(WRITE_GUARD)),
        "pre-push": PRE_PUSH_TEMPLATE.replace("__HARNESS__", str(HARNESS)).replace("__AGENT_RUNTIME__", str(AGENT_RUNTIME)).replace("__HARNESS_POLICY__", str(HARNESS_POLICY)),
    }
    installed: list[str] = []
    skipped: list[str] = []
    repaired: list[str] = []
    backups: list[str] = []
    for name in sorted(selected):
        content = targets[name]
        target = git_dir / "hooks" / name
        broken = managed_broken_hook(target)
        if target.exists() and not force and not broken:
            skipped.append(str(target))
            continue
        if target.exists():
            backups.append(str(backup_hook(target)))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        target.chmod(0o755)
        installed.append(str(target))
        if broken:
            repaired.append(str(target))
    status = "repaired" if repaired else "installed" if installed else "skipped"
    return {
        "repo": str(repo),
        "git_dir": str(git_dir),
        "status": status,
        "installed": installed,
        "repaired": repaired,
        "backups": backups,
        "skipped": skipped,
        "blockers": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Install workspace write guard pre-commit and Harness pre-push hooks")
    parser.add_argument("--repo", action="append", required=True)
    parser.add_argument("--hook", action="append", choices=["pre-commit", "pre-push"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    hook_names = set(args.hook) if args.hook else None
    results = [install(Path(repo), args.force, hook_names) for repo in args.repo]
    decision = "block" if any(item.get("status") == "blocked" for item in results) else "pass"
    print(json.dumps({"schema": "codex-write-guard-hook-install-v1", "decision": decision, "results": results}, ensure_ascii=False, indent=2))
    return 1 if decision == "block" else 0


if __name__ == "__main__":
    raise SystemExit(main())
