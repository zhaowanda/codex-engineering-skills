---
name: implementation-completion-gate
description: Validate that implementation is complete before review, testing, or release. Use after code edits to require real diff evidence, delivery-plan scope alignment, changed files, implementation summary, and follow-up evidence plan.
category: workflow-gate
maturity: expert-gate
stage: post-implementation-review
gate: true
---

# Implementation Completion Gate

Use this skill immediately after file edits and before review or test evidence is accepted.

## Position

```text
file edits
-> implementation-completion-gate
-> diff-impact-analyzer
-> code-design-quality-reviewer / code-review-gate
```

## Rules

- Require a real diff file; empty or missing diffs cannot prove implementation completion.
- Block when the supplied delivery plan is `needs_completion`/`block`, has unresolved `open_gates`, or carries a `source_design_gate` that disallows design or implementation.
- Check changed files against delivery-plan scope when a plan is supplied.
- Require a concrete implementation summary, not a generic placeholder.
- Emit structured follow-up evidence requirements for risky implementation surfaces: API contracts, database/schema/query changes, MQ producer/consumer flow, cache consistency, transaction/idempotency, permission/data-scope enforcement, frontend browser behavior, configuration, and observability.
- Warn on follow-up evidence gaps that must be handled by review, test, release, or production-observation gates.
- Treat this as completion evidence only; it does not replace code review or test execution.

## Command

```bash
python3 scripts/implementation_complete.py \
  --diff-file /path/to/change.diff \
  --delivery-plan artifacts/REQ-001/delivery_plan.json \
  --summary "implemented scoped change" \
  --out artifacts/REQ-001/implementation_completion_gate.json
```

## Output

The output uses schema `codex-implementation-completion-v1`.

The artifact reports changed files, scope alignment, summary quality, blockers, warnings, and `evidence_followups`. Follow-up items must be closed by later review/test/release evidence rather than ignored as informal notes.
