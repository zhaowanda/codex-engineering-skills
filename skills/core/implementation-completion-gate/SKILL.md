---
name: implementation-completion-gate
description: Validate that implementation is complete before review, testing, or release. Use after code edits to require real diff evidence, delivery-plan scope alignment, changed files, implementation summary, and follow-up evidence plan.
---

# Implementation Completion Gate

## Command

```bash
python3 skills/core/implementation-completion-gate/scripts/implementation_complete.py \
  --diff-file /path/to/change.diff \
  --delivery-plan artifacts/REQ-001/delivery_plan.json \
  --summary "implemented scoped change" \
  --out artifacts/REQ-001/implementation_completion_gate.json
```

## Output

The output uses schema `codex-implementation-completion-v1`.
