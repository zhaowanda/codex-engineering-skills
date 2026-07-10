---
name: domain-model-governor
description: Generate domain model artifacts for business objects, lifecycle, state machine, invariants, business rules, exception paths, and clarification gaps. Use when requirements involve non-trivial business process, status changes, batch operations, approvals, settlement, renewal, orders, payments, or cross-step workflows.
category: artifact-generator
maturity: expert-gate
stage: design
gate: true
---

# Domain Model Governor

Use this skill after `spec-governor` and before detailed technical design for business-heavy requirements.

## Position

Run before API, data, technical, and test design when the requirement has real business process or state behavior.

## Rules

- Generate `domain_model_design.json`.
- Model real business purpose before implementation mechanics.
- Cover business objects, lifecycle, state transitions, invariants, business rules, trigger conditions, preconditions, postconditions, and exception paths.
- Block if the business goal, actor, trigger, state transition, or completion condition is ambiguous.

## Command

```bash
python3 scripts/domain_model.py \
  --spec artifacts/REQ-001/spec.json \
  --out artifacts/REQ-001/domain_model_design.json
```

## Output

The script writes `codex-domain-model-design-v1` with `decision`, `business_objects`, `state_machine`, `invariants`, `rules`, and `clarification_questions`.
