---
name: test-design-governor
description: Generate and validate test design artifacts before implementation. Use when a spec, technical design, architecture design, or delivery plan needs functional, regression, integration, permission, frontend, configuration, performance, and release test scope before coding.
category: workflow-gate
maturity: expert-gate
stage: testing
gate: true
---

# Test Design Governor

Use this skill after design and before implementation.

## Commands

```bash
python3 scripts/test_design.py \
  render \
  --spec artifacts/REQ-001/spec.json \
  --technical-design artifacts/REQ-001/technical_design.json \
  --architecture-design artifacts/REQ-001/architecture_design.json \
  --out artifacts/REQ-001/test_design.json
```

```bash
python3 scripts/test_design.py \
  validate \
  --file artifacts/REQ-001/test_design.json
```

## Rules

- Every acceptance criterion needs at least one test case.
- Permission-sensitive requirements need negative permission cases.
- Cross-repo changes need integration tests.
- UI changes need frontend/browser acceptance evidence.
- Performance/security/config signals must be reflected in test scope.
- Cases that need fixtures, accounts, roles, tenants, or records must declare `test_data_refs`, setup preconditions, and cleanup expectations.
- Generate `test_data_plan.json` with `test-data-governor` before real execution when test data refs exist.

## Output

The output uses schema `codex-test-design-v1`.

Key fields:

- `test_cases[].test_data_refs`
- `test_cases[].data_requirements`
- `test_cases[].cleanup_expectations`
- `test_data_plan_ref`
