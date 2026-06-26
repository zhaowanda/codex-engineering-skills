---
name: workspace-write-guard
description: Audit workspace writes against edit permits. Use before and after AI-assisted file edits, in pre-commit hooks, or when built-in edit tools may bypass the edit-readiness wrapper.
---

# Workspace Write Guard

Use this as the write-layer backstop for direct edits such as `apply_patch`.

## Position

```text
edit-readiness-governor permit
-> workspace-write-guard snapshot
-> file edits
-> workspace-write-guard audit
-> code review / commit
```

## Rules

- Create a snapshot after a valid edit permit and before direct file edits.
- Audit after edits and before review, commit, push, or release evidence.
- Changed files must stay inside `permit.allowed_files` when the permit binds file scope.
- Current repo, branch, doc id, permit decision, and permit expiry must still match.
- Files modified before the permit was issued are suspicious and block the audit.
- If `decision=blocked`, do not commit, push, or count the change as delivery evidence.

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

Install a pre-commit hook:

```bash
python3 scripts/install_pre_commit.py \
  --repo /path/to/repo
```

At commit time set:

```bash
export CODEX_EDIT_PERMIT=/path/to/edit_permit.json
export CODEX_WRITE_GUARD_SNAPSHOT=/path/to/write_guard_snapshot.json
export CODEX_DOC_ID=REQ-001-checkout
```

## Output

- Snapshot schema: `codex-write-guard-snapshot-v1`
- Audit schema: `codex-write-guard-audit-v1`

The audit report lists changed files, files ignored as evidence artifacts, unauthorized files, and files whose modification time predates permit issuance.
