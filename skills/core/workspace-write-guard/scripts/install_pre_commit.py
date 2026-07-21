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

resolve_artifact_dir() {
  if [[ -n "$ARTIFACT_DIR" ]]; then
    printf '%s\\n' "$ARTIFACT_DIR"
    return 0
  fi

  local configured configured_path
  configured="$(git config --get codex.artifactDir || true)"
  if [[ -n "$configured" ]]; then
    if [[ "$configured" = /* ]]; then
      configured_path="$configured"
    else
      configured_path="$REPO/$configured"
    fi
    if [[ -d "$configured_path" ]]; then
      (cd "$configured_path" && pwd)
      return 0
    fi
  fi

  local marker marker_value marker_doc_id
  for marker in "$REPO/.codex/current_delivery.json" "$REPO/../.codex/current_delivery.json"; do
    if [[ -f "$marker" ]]; then
      marker_value="$(
        python3 - "$marker" <<'PY' || true
import json
import sys
from pathlib import Path

try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    data = {}
for key in ("artifact_dir", "artifacts_dir", "delivery_artifact_dir"):
    value = str(data.get(key) or "")
    if value:
        print(value)
        raise SystemExit(0)
delivery = data.get("delivery")
if isinstance(delivery, dict):
    value = str(delivery.get("artifact_dir") or delivery.get("artifacts_dir") or "")
    if value:
        print(value)
PY
      )"
      if [[ -n "$marker_value" ]]; then
        if [[ "$marker_value" = /* ]]; then
          candidate="$marker_value"
        else
          candidate="$REPO/$marker_value"
        fi
        if [[ -d "$candidate" ]]; then
          (cd "$candidate" && pwd)
          return 0
        fi
      fi
      marker_doc_id="$(
        python3 - "$marker" <<'PY' || true
import json
import sys
from pathlib import Path

try:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
except Exception:
    data = {}
for key in ("doc_id", "docId", "requirement_id", "requirementId"):
    value = str(data.get(key) or "")
    if value:
        print(value)
        raise SystemExit(0)
delivery = data.get("delivery")
if isinstance(delivery, dict):
    for key in ("doc_id", "docId", "requirement_id", "requirementId"):
        value = str(delivery.get(key) or "")
        if value:
            print(value)
            raise SystemExit(0)
PY
      )"
      if [[ -n "$marker_doc_id" ]]; then
        break
      fi
    fi
  done

  local branch doc_id normalized_doc_id configured_doc_id candidate docs_root slug matches match_count
  branch="$(git branch --show-current || true)"
  configured_doc_id="$(git config --get codex.docId || true)"
  doc_id="${CODEX_DOC_ID:-${configured_doc_id:-${marker_doc_id:-}}}"
  if [[ -z "$doc_id" && "$branch" =~ (REQ[-_A-Za-z0-9]+) ]]; then
    doc_id="${BASH_REMATCH[1]}"
  fi
  if [[ -n "$doc_id" ]]; then
    normalized_doc_id="$(
      python3 - "$doc_id" <<'PY'
import re
import sys

value = sys.argv[1]
print(re.sub(r"^req", "REQ", value, flags=re.IGNORECASE))
PY
    )"
    for candidate in \
      "$REPO/.codex/artifacts/$doc_id" \
      "$REPO/.codex/artifacts/$normalized_doc_id" \
      "$REPO/artifacts/$doc_id" \
      "$REPO/artifacts/$normalized_doc_id" \
      "$REPO/../company-delivery-docs/deliveries/$doc_id/artifacts" \
      "$REPO/../company-delivery-docs/deliveries/$normalized_doc_id/artifacts" \
      "$REPO/../../company-delivery-docs/deliveries/$doc_id/artifacts" \
      "$REPO/../../company-delivery-docs/deliveries/$normalized_doc_id/artifacts"; do
      if [[ -d "$candidate" ]]; then
        (cd "$candidate" && pwd)
        return 0
      fi
    done
    slug="$(
      python3 - "$normalized_doc_id" <<'PY'
import re
import sys

value = sys.argv[1]
match = re.match(r"^REQ[-_]\\d{8}[-_](.+)$", value, flags=re.IGNORECASE)
if match:
    print(match.group(1))
PY
    )"
    if [[ -n "$slug" ]]; then
      for docs_root in "$REPO/../company-delivery-docs/deliveries" "$REPO/../../company-delivery-docs/deliveries"; do
        if [[ -d "$docs_root" ]]; then
          matches=()
          while IFS= read -r candidate; do
            matches+=("$candidate")
          done < <(find "$docs_root" -mindepth 2 -maxdepth 2 -type d -path "$docs_root/REQ-*-$slug/artifacts" | sort)
          match_count="${#matches[@]}"
          if [[ "$match_count" -eq 1 ]]; then
            (cd "${matches[0]}" && pwd)
            return 0
          fi
          if [[ "$match_count" -gt 1 ]]; then
            echo "workflow-harness: ambiguous artifact dirs for doc slug '$slug': ${matches[*]}" >&2
            return 1
          fi
        fi
      done
    fi
  fi
}

if [[ -z "$ARTIFACT_DIR" ]]; then
  ARTIFACT_DIR="$(resolve_artifact_dir || true)"
fi

if [[ -z "$ARTIFACT_DIR" ]]; then
  echo "workflow-harness: CODEX_ARTIFACT_DIR could not be resolved before push" >&2
  echo "workflow-harness: set CODEX_ARTIFACT_DIR, git config codex.artifactDir, git config codex.docId, or create .codex/current_delivery.json" >&2
  exit 1
fi

if [[ ! -d "$ARTIFACT_DIR" ]]; then
  echo "workflow-harness: artifact dir does not exist: $ARTIFACT_DIR" >&2
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
