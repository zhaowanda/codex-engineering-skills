---
name: test-data-governor
description: Generate and validate test data plans for test cases. Use after test-design-governor and before test execution when test cases need fixtures, accounts, roles, tenants, records, cleanup rules, or synthetic data safety evidence.
category: workflow-gate
maturity: expert-gate
stage: testing
gate: true
---

# Test Data Governor

Use this skill after `test_design.json` exists and before running test cases.

## Commands

```bash
python3 scripts/test_data.py \
  render \
  --test-design artifacts/REQ-001/test_design.json \
  --out artifacts/REQ-001/test_data_plan.json
```

```bash
python3 scripts/test_data.py \
  validate \
  --file artifacts/REQ-001/test_data_plan.json
```

## Rules

- Every test case that needs data must map to at least one dataset.
- Carry `requirements_understanding_gate` and the source test design decision. If the source test design is blocked, or requirement understanding disallows design/implementation, the test data plan must return `decision=block`.
- Use synthetic or anonymized data only.
- Block plans that declare real sensitive data, production data, missing cleanup, missing setup method, or missing case links.
- Permission cases must include role/account data.
- Frontend/integration cases must include environment or dependency preconditions.
- Do not prepare executable fixtures for ambiguous requirements; clarify the requirement and regenerate test design first.

## Output

The output uses schema `codex-test-data-plan-v1`.

Decision values:

- `pass`
- `block`
