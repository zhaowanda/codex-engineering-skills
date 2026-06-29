---
name: test-evidence-gate
description: Validate real test and CI execution evidence before release evidence binding. Use after implementation review when a change needs proof that functional tests, regression scope, CI commands, and optional frontend acceptance actually ran and passed.
category: workflow-gate
maturity: expert-gate
stage: testing
gate: true
---

# Test Evidence Gate

Use this skill after code review and before release evidence binding.

## Position

```text
implementation
-> code-review-gate
-> test-evidence-gate
-> release evidence binder
```

## Rules

- `block` if `test_execution_evidence.json` is missing.
- `block` if test evidence has no real executed cases or command/API/UI evidence.
- `block` if `failed_cases` or `untested_blockers` exist.
- `block` if CI has failed commands, unknown commands, manual-review-required commands, or plan-only mode.
- `block` if `--require-frontend` is set and frontend acceptance is missing or failed.
- `pass` only when required evidence exists, no blockers remain, and the minimum executed-case threshold is met.

This gate does not advance delivery state automatically. If the result passes, run your delivery-state advancement command as a separate explicit step.

## Command

```bash
python3 scripts/test_evidence_gate.py \
  --artifact-dir artifacts/review \
  --out artifacts/review/test_evidence_gate.json
```

Require frontend browser evidence:

```bash
python3 scripts/test_evidence_gate.py \
  --artifact-dir artifacts/review \
  --require-frontend \
  --out artifacts/review/test_evidence_gate.json
```

## Expected Artifact Names

The gate reads:

- `test_execution_evidence.json`
- `ci_execution_evidence.json`
- `frontend_acceptance.json`

## Output

The output uses schema `codex-test-evidence-gate-v1`.

Decision values:

- `pass`
- `block`
