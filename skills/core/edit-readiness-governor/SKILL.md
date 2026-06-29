---
name: edit-readiness-governor
description: Enforce the final pre-edit gate before AI-assisted source, config, test, or documentation writes. Use immediately before file edits to verify doc id, design artifacts, delivery plan scope, delivery state, Git branch readiness, and a short-lived edit permit.
category: workflow-gate
maturity: expert-gate
stage: edit-readiness
gate: true
---

# Edit Readiness Governor

Use this skill immediately before the first file write in each repository.

## Position

```text
spec/design/plan
-> delivery-state-governor
-> git-worktree-governor
-> edit-readiness-governor assert
-> edit-readiness-governor permit
-> file edits
```

## Rules

- Read-only exploration can happen before this gate.
- Any source/config/test/doc write requires `decision=ready`.
- Every non-exploratory change needs a stable `doc_id`.
- Git evidence must come from `git-worktree-governor` and be `decision=ready`.
- Current branch must match the Git evidence branch and must not be `master` or `main`.
- If a delivery state is provided, it must validate for `implementation`.
- Standard, large, and migration lanes require design-first evidence before editing.
- Bugfix, hotfix, and small-change lanes still need a doc id, Git evidence, and lane-appropriate lightweight evidence.
- Allowed files should be bound into the permit; files outside the permit require a new permit.
- Treat `decision=blocked` as a hard stop.

## Commands

Assert readiness:

```bash
python3 scripts/edit_readiness.py \
  assert \
  --repo /path/to/repo \
  --doc-id REQ-001-checkout \
  --lane standard_requirement \
  --git-evidence artifacts/git/repo-a-git_baseline_evidence.json \
  --delivery-state artifacts/delivery_state.json \
  --spec artifacts/spec.json \
  --technical-design artifacts/technical_design.json \
  --architecture-design artifacts/architecture_design.json \
  --delivery-plan artifacts/delivery_plan.json \
  --design-review artifacts/design_review.json \
  --docs-quality artifacts/docs_quality.json \
  --allowed-file src/checkout/service.py
```

Create a short-lived edit permit:

```bash
python3 scripts/edit_readiness.py \
  permit \
  --repo /path/to/repo \
  --doc-id REQ-001-checkout \
  --lane standard_requirement \
  --git-evidence artifacts/git/repo-a-git_baseline_evidence.json \
  --delivery-state artifacts/delivery_state.json \
  --spec artifacts/spec.json \
  --technical-design artifacts/technical_design.json \
  --architecture-design artifacts/architecture_design.json \
  --delivery-plan artifacts/delivery_plan.json \
  --design-review artifacts/design_review.json \
  --docs-quality artifacts/docs_quality.json \
  --allowed-file src/checkout/service.py \
  --ttl-minutes 30 \
  --out artifacts/edit_permit.json
```

Verify permit before a write:

```bash
python3 scripts/edit_readiness.py \
  verify-permit \
  --permit artifacts/edit_permit.json \
  --repo /path/to/repo \
  --doc-id REQ-001-checkout \
  --branch feature/REQ-001-checkout \
  --allowed-file src/checkout/service.py
```

Wrap scripted writes:

```bash
python3 scripts/pre_edit_wrapper.py \
  --permit artifacts/edit_permit.json \
  --repo /path/to/repo \
  --doc-id REQ-001-checkout \
  --branch feature/REQ-001-checkout \
  --allowed-file src/checkout/service.py \
  --dry-run \
  -- touch /tmp/example
```

## Output

Readiness output uses schema `codex-edit-readiness-v1`.

Permit output uses schema `codex-edit-permit-v1` and is valid only for the bound repo, branch, doc id, files, evidence paths, and expiry window.
