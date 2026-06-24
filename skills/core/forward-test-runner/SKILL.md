---
name: forward-test-runner
description: Run forward tests for synthetic open-core cases and validate expected schemas, decisions, blockers, and next commands. Use before releases to ensure skills still work end to end without relying on private context.
---

# Forward Test Runner

## Command

```bash
python3 skills/core/forward-test-runner/scripts/forward_test.py \
  --root .
```

## Output

The output uses schema `codex-forward-test-run-v1`.
