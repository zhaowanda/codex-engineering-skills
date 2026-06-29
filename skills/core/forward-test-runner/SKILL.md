---
name: forward-test-runner
description: Run forward tests for synthetic open-core cases and validate expected schemas, decisions, blockers, and next commands. Use before releases to ensure skills still work end to end without relying on private context.
category: template-runner
maturity: orchestrator
stage: workflow-orchestration
gate: false
---

# Forward Test Runner

Use this skill before releases to ensure synthetic workflow expectations still pass.

## Position

```text
skill/framework changes
-> forward-test-runner
-> benchmark-governor
-> release-package-governor
```

## Rules

- Run only open-core synthetic cases; do not depend on private repositories or overlays.
- Validate expected schemas, decisions, blockers, and next commands.
- Treat changed expected behavior as requiring an explicit test fixture update.
- Block release when synthetic cases fail unexpectedly.
- Keep generated outputs in temporary or explicit artifact directories.

## Command

```bash
python3 scripts/forward_test.py \
  --root .
```

## Output

The output uses schema `codex-forward-test-run-v1`.

The artifact reports cases, pass/fail status, schema checks, decision checks, blockers, and warnings.
