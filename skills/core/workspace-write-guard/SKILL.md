---
name: workspace-write-guard
description: Audit workspace writes against edit permits. Use before and after AI-assisted file edits, in pre-commit hooks, or when built-in edit tools may bypass the edit-readiness wrapper.
category: workflow-gate
maturity: expert-gate
stage: edit-readiness
gate: true
---

# Workspace Write Guard

Use this as the write-layer backstop for direct edits such as `apply_patch`.

## Position

```text
edit-readiness-governor permit
-> Agent Runtime pre-edit authorization
-> workspace-write-guard snapshot
-> file edits
-> workspace-write-guard audit
-> Agent Runtime post-implementation / pre-push checkpoints
-> code review / commit
```

## Rules

- Create a snapshot after a valid edit permit and before direct file edits.
- Audit after edits and before review, commit, push, or release evidence.
- Changed files must stay inside `permit.allowed_files` when the permit binds file scope.
- Current repo, branch, doc id, permit decision, and permit expiry must still match.
- Repo and permit repo must not point to `_staging`; write evidence is valid only from the registered project checkout.
- Files modified before the permit was issued are suspicious and block the audit.
- If `decision=blocked`, do not commit, push, or count the change as delivery evidence.
- Treat built-in editor and MCP writes as imported Runtime events, then use the write audit as the authoritative filesystem backstop.
- Treat a missing hook script or stale absolute hook path as an installation defect. Repair the hook and rerun the original Git command; never accept `git commit --no-verify` or `git push --no-verify` as delivery evidence or a successful governed path.

## Commands

Create a snapshot:

```bash
python3 scripts/write_guard.py \
  snapshot \
  --repo /path/to/repo \
  --permit artifacts/edit_permit.json \
  --out artifacts/write_guard_snapshot.json
```

Audit after edits:

```bash
python3 scripts/write_guard.py \
  audit \
  --repo /path/to/repo \
  --permit artifacts/edit_permit.json \
  --snapshot artifacts/write_guard_snapshot.json \
  --out artifacts/write_guard_audit.json
```

Fail fast in hooks:

```bash
python3 scripts/write_guard.py \
  hook-check \
  --repo /path/to/repo \
  --permit artifacts/edit_permit.json \
  --snapshot artifacts/write_guard_snapshot.json
```

Install the pre-commit write guard and pre-push Harness hooks:

```bash
python3 scripts/install_pre_commit.py \
  --repo /path/to/repo
```

Default installation uses hook profile `framework_light`: install `pre-commit` plus a lightweight `pre-push` hook that checks repository context and blocks pushes with tracked workspace changes, but does not require delivery evidence artifacts.

Install strict delivery pre-push enforcement only for delivery repositories:

```bash
python3 scripts/install_pre_commit.py \
  --repo /path/to/repo \
  --hook-profile delivery_strict
```

Disable pre-push installation and keep only `pre-commit`:

```bash
python3 scripts/install_pre_commit.py \
  --repo /path/to/repo \
  --hook-profile off
```

Repair only a missing or stale pre-push hook without installing pre-commit:

```bash
python3 scripts/install_pre_commit.py \
  --repo /path/to/repo \
  --hook pre-push \
  --hook-profile delivery_strict
```

The installer resolves the actual Git directory, including linked worktrees, verifies the Harness and Agent Runtime scripts before writing a hook, and automatically repairs known Codex hooks whose absolute script target no longer exists. Replaced hooks are retained beside the active hook as timestamped `*.codex-backup.*` files. Existing non-Codex hooks are preserved unless `--force` is explicit.

Hook profiles:

- `framework_light`: lightweight repository pre-push guard; no delivery artifact resolution and no post-implementation evidence enforcement.
- `delivery_strict`: full delivery pre-push Harness. It uses `CODEX_ARTIFACT_DIR` when set. If it is not set, it resolves artifacts from `git config codex.artifactDir`, `.codex/current_delivery.json`, `CODEX_DOC_ID`, `git config codex.docId`, or a branch/doc id such as `REQ-001` under `company-delivery-docs/deliveries/<doc-id>/artifacts`. For historical doc-id drift, it may resolve a unique `REQ-YYYYMMDD-<slug>` match in the unified docs repo; multiple matches remain blocked. It advances the Runtime `pre_push` checkpoint, then runs the `pre_push` Harness against the current repository and blocks missing post-implementation Harness evidence, project-skill-index synchronization, incomplete review/test evidence, or test evidence bound to another commit.
- `off`: do not install `pre-push`.

At commit time set:

```bash
export CODEX_EDIT_PERMIT=/path/to/edit_permit.json
export CODEX_WRITE_GUARD_SNAPSHOT=/path/to/write_guard_snapshot.json
export CODEX_DOC_ID=REQ-001-checkout
export CODEX_ARTIFACT_DIR=/path/to/artifacts/REQ-001-checkout
```

## Output

- Snapshot schema: `codex-write-guard-snapshot-v1`
- Audit schema: `codex-write-guard-audit-v1`
- Runtime hook artifact: `runtime/checkpoints/pre_push.json` using `codex-runtime-checkpoint-v1`
- Harness hook artifact: `harness/pre_push.json` using `codex-harness-checkpoint-v2`

The audit report lists changed files, files ignored as evidence artifacts, unauthorized files, and files whose modification time predates permit issuance.
