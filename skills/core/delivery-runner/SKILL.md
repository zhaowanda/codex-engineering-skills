---
name: delivery-runner
description: Inspect a delivery artifact folder and report current workflow stage, blockers, next command, and whether implementation or release is allowed. Use as the one-command entrypoint after spec/design/plan/git/review/test/release artifacts exist or when the user asks where the process is.
category: template-runner
maturity: orchestrator
stage: delivery-planning
gate: false
---

# Delivery Runner

Use this skill as the workflow status entrypoint.

## Command

```bash
python3 scripts/delivery_runner.py \
  inspect \
  --artifact-dir artifacts/REQ-001
```

## Rules

- Prefer `delivery_state.json` when present.
- Also inspect key artifacts directly so users can see missing files.
- Block implementation until spec, technical design, architecture design, test design, delivery plan, delivery plan review, design review, docs quality, delivery docs readiness, git, and edit readiness are complete.
- Delivery docs readiness requires a docs root, doc manifest, and Git repository.
- Git readiness requires evidence that each modify repository fetched the remote and updated the base branch with `pull --ff-only`.
- Report `delivery_plan_review` as the next stage before Git or edit readiness when `delivery_plan_review.json` is missing or blocked.
- Block release until implementation, review, test, and release evidence are complete.

## Output

The output uses schema `codex-delivery-runner-status-v1`.
