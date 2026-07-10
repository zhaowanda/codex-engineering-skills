---
name: delivery-plan-reviewer
description: Review delivery plans for executable task depth before Git preparation, edit permits, implementation, or release. Use after delivery-plan-templates to block shallow tasks, broad file scope, missing evidence, unresolved gates, and incomplete rollback controls.
category: workflow-gate
maturity: expert-gate
stage: delivery-planning
gate: true
---

# Delivery Plan Reviewer

Use this skill after a delivery plan is generated and before Git preparation or edit readiness.

## Position

```text
delivery-plan-templates
-> delivery-plan-reviewer
-> git-worktree-governor
-> edit-readiness-governor
```

## Rules

- Block implementation if `open_gates` is not empty.
- Block implementation if `source_design_gate.design_allowed=false` or `source_design_gate.implementation_allowed=false`; requirement clarification must be resolved and design review rerun before executable tasks are accepted.
- Every `modify` repo must have concrete tasks, narrow `allowed_files`, `read_first`, `test_commands`, acceptance evidence, rollback steps, and risk controls.
- Tasks should include executable phases such as read, confirm, edit, test, evidence, and rollback verification.
- Each task must include concrete files, implementation notes, evidence, rollback check, dependencies, blockers, and exit criteria; summary-only tasks are not executable.
- Git preparation must include fetch, `pull --ff-only`, branch setup, and clean worktree verification before edits.
- File scope must not be empty or overly broad.
- Validation plan must map acceptance criteria to required evidence.
- Release and rollback order must include every modified repository.

## Commands

Review a delivery plan:

```bash
python3 scripts/delivery_plan_review.py \
  review \
  --file artifacts/delivery_plan.json \
  --out artifacts/delivery_plan_review.json
```

Validate a review artifact:

```bash
python3 scripts/delivery_plan_review.py \
  validate \
  --file artifacts/delivery_plan_review.json
```

## Output

The output uses schema `codex-delivery-plan-review-v1`.

Implementation is allowed only when `decision=pass`, score is at least 85, and no blocker/high finding remains.
