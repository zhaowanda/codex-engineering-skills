---
name: code-design-quality-reviewer
description: Review implemented or proposed code diffs for design quality before bug-first review, testing, or release. Use to detect cohesion, coupling, responsibility boundary, abstraction, API contract, permission, transaction, performance, security, configuration, financial correctness, testability, and maintainability risks.
category: workflow-gate
maturity: expert-gate
stage: post-implementation-review
gate: true
---

# Code Design Quality Reviewer

Use this skill after implementation or when reviewing a proposed diff.

## Position

```text
implementation
-> workspace-write-guard audit
-> code-design-quality-reviewer
-> code review gate
-> tests
-> release evidence
```

## Rules

- `block` if code crosses critical boundaries, logs sensitive data, hardcodes secrets, or makes rollback/testing unsafe.
- `needs_refactor` if behavior may work but cohesion, coupling, abstraction, performance, permission, or testability materially degrades.
- `pass` only when there are no active blocker/high/medium findings.
- Treat this as a first-pass gate. Add human/Codex review for file-line reasoning on serious findings.
- Every finding has a stable id and lifecycle status.
- Active `blocker/high` findings cannot pass release.
- Closed statuses require resolution evidence.

## Commands

Review a diff file:

```bash
python3 scripts/design_quality.py \
  review \
  --diff-file artifacts/change.diff \
  --requirement-id REQ-001-checkout \
  --design-ref technical_design.design_traceability_matrix \
  --test-ref AC-1 \
  --owner owner-name \
  --out artifacts/code_design_quality.json
```

Validate review output:

```bash
python3 scripts/design_quality.py \
  validate \
  --file artifacts/code_design_quality.json
```

Resolve a finding:

```bash
python3 scripts/design_quality.py \
  resolve \
  --file artifacts/code_design_quality.json \
  --finding-id CDQR-XXXXXXXXXX \
  --status recheck_passed \
  --resolution "Refactored into service layer and verified by API test"
```

## Output

The review output uses schema `codex-code-design-quality-review-v1`.

Main decisions:

- `pass`
- `needs_refactor`
- `block`
