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
- Carry `requirements_understanding_gate` from spec/technical/architecture design, including business closure, state machine completeness, business goal quality, repository impact, dependency chain, and runtime dependency graph models. If `design_allowed=false` or `implementation_allowed=false`, the test design artifact may be generated only as a blocked clarification draft and validation must return `decision=block`.
- Permission-sensitive requirements need negative permission cases.
- Cross-repo changes need integration tests.
- UI changes need frontend/browser acceptance evidence.
- Performance/security/config signals must be reflected in test scope.
- Cases that need fixtures, accounts, roles, tenants, or records must declare `test_data_refs`, setup preconditions, and cleanup expectations.
- Acceptance-mapped cases must declare `execution_required: "must_run"`; they are not advisory checklist items.
- Cases must declare `execution_mode` so later evidence can distinguish automated, manual, browser, API, integration, or blocked execution paths.
- Generate `test_data_plan.json` with `test-data-governor` before real execution when test data refs exist.
- Do not treat generated test cases as executable while requirement understanding is blocked; clarify business purpose, flow, entrypoints/triggers, and acceptance criteria first.
- Build execution paths from confirmed source anchors when source-location evidence is available.
- Block executable test design when code locations are unconfirmed; never copy rejected candidates into page, API, or data paths.

## Output

The output uses schema `codex-test-design-v1`.

Key fields:

- `test_cases[].test_data_refs`
- `test_cases[].data_requirements`
- `test_cases[].cleanup_expectations`
- `test_cases[].execution_required`
- `test_cases[].execution_mode`
- `test_data_plan_ref`
