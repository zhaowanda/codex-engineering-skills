---
name: code-review-gate
description: Aggregate post-implementation review evidence into one code review gate. Use after implementation to combine bug-first review, code design quality, write guard audit, security/performance evidence, tests, CI, frontend acceptance, configuration readiness, and release blockers.
---

# Code Review Gate

Use this skill after implementation and before test/release evidence binding.

## Position

```text
implementation
-> workspace-write-guard audit
-> code-design-quality-reviewer
-> code-review-gate
-> test evidence gate
-> release evidence binder
```

## Rules

- `block` if any active blocker/high finding exists in code review, design quality, security, performance, or write audit evidence.
- `block` if write guard audit is not ready.
- `block` if CI failed, tests failed, frontend acceptance failed, configuration readiness is blocked, or release blockers exist.
- `request_changes` if medium findings, missing evidence, unresolved evidence gaps, unknown CI commands, or incomplete performance evidence remain.
- `approve` only when required evidence exists, active severe/medium findings are closed, and residual risks have owner and resolution.
- This gate does not replace source-level review. It decides whether the review stage is closed.

## Command

```bash
python3 skills/core/code-review-gate/scripts/review_gate.py \
  --artifact-dir artifacts/review \
  --out artifacts/review/code_review_gate.json
```

## Expected Artifact Names

The gate reads these files when present:

- `code_review.json`
- `code_design_quality.json`
- `write_guard_audit.json`
- `data_security_review.json`
- `performance_diff_review.json`
- `performance_design_review.json`
- `test_execution_evidence.json`
- `ci_execution_evidence.json`
- `frontend_acceptance.json`
- `configuration_readiness.json`
- `evidence_gap_summary.json`

## Output

The output uses schema `codex-code-review-gate-v1`.

Decision values:

- `approve`
- `request_changes`
- `block`
