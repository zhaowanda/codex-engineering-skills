---
name: delivery-runner
description: Inspect a delivery artifact folder and report current workflow stage, blockers, next command, and whether implementation or release is allowed. Use as the one-command entrypoint after spec/design/plan/git/review/test/release artifacts exist or when the user asks where the process is.
---

# Delivery Runner

Use this skill as the workflow status entrypoint.

## Command

```bash
python3 skills/core/delivery-runner/scripts/delivery_runner.py \
  inspect \
  --artifact-dir artifacts/REQ-001
```

## Rules

- Prefer `delivery_state.json` when present.
- Also inspect key artifacts directly so users can see missing files.
- Block implementation until spec, designs, delivery plan, design review, git, and edit readiness are complete.
- Block release until implementation, review, test, and release evidence are complete.

## Output

The output uses schema `codex-delivery-runner-status-v1`.
