---
name: git-worktree-governor
description: Prepare and verify clean Git worktrees before AI-assisted code edits. Use after delivery planning and before implementation to fetch latest base branch, create feature branches, prepare all modify repositories from a delivery plan, and block edits on default branches or dirty worktrees.
---

# Git Worktree Governor

Use this skill before any source/config/test edit in a Git repository.

## Position

```text
delivery_plan
-> git-worktree-governor
-> edit readiness
-> implementation
```

## Rules

- Read-only code inspection may happen before this gate.
- File edits must not happen until this gate returns `decision=ready`.
- Worktree must be clean before branch preparation.
- Base branch must be fetched and updated with `pull --ff-only`.
- Implementation must happen on a non-default branch, never directly on `master` or `main`.
- Every `repo_tasks[].role=modify` repository in a delivery plan must be prepared before implementation starts.
- `confirm_only`, `read_only`, and `out_of_scope` repositories must not be branched.
- If the helper reports blockers, stop and resolve them before editing files.

## Commands

Check one repository:

```bash
python3 skills/core/git-worktree-governor/scripts/git_worktree.py \
  check \
  --repo /path/to/repo \
  --base-branch main
```

Prepare one repository:

```bash
python3 skills/core/git-worktree-governor/scripts/git_worktree.py \
  prepare \
  --repo /path/to/repo \
  --base-branch main \
  --branch feature/REQ-001-checkout \
  --artifact-dir artifacts/git
```

Prepare all modify repositories from a generic delivery plan:

```bash
python3 skills/core/git-worktree-governor/scripts/git_worktree.py \
  prepare-plan \
  --delivery-plan artifacts/delivery_plan.json \
  --doc-id REQ-001-checkout \
  --branch-prefix feature \
  --artifact-dir artifacts/git
```

Assert readiness immediately before edits:

```bash
python3 skills/core/git-worktree-governor/scripts/git_worktree.py \
  assert-ready \
  --repo /path/to/repo \
  --branch feature/REQ-001-checkout \
  --evidence-file artifacts/git/repo-a-git_baseline_evidence.json
```

## Delivery Plan Contract

`prepare-plan` expects explicit repository paths. It does not read private project registries.

```json
{
  "repo_tasks": [
    {
      "repo": "repo-a",
      "repo_path": "/path/to/repo-a",
      "role": "modify",
      "base_branch": "main"
    },
    {
      "repo": "repo-b",
      "repo_path": "/path/to/repo-b",
      "role": "read_only"
    }
  ]
}
```

Only `role=modify` tasks are prepared.

## Evidence

Single-repo preparation writes `git_baseline_evidence.json`:

```json
{
  "schema": "codex-git-baseline-evidence-v1",
  "repo": "/path/to/repo",
  "base_branch": "main",
  "new_branch": "feature/REQ-001-checkout",
  "status_clean_before": true,
  "fetched": true,
  "base_updated": true,
  "created_branch": true,
  "current_branch": "feature/REQ-001-checkout",
  "baseline_commit": "",
  "blockers": [],
  "warnings": [],
  "decision": "ready"
}
```

Plan preparation writes:

```text
git_plan_baseline_summary.json
<repo>-git_baseline_evidence.json
```

Edit readiness evidence uses schema `codex-git-edit-readiness-v1`.
