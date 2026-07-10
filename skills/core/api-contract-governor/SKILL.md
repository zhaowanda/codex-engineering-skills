---
name: api-contract-governor
description: Generate API contract design artifacts for endpoint naming, request/response, errors, permissions, idempotency, compatibility, and consumer impact. Use when requirements affect APIs, routes, service contracts, frontend-backend calls, or cross-repository integrations.
category: artifact-generator
maturity: expert-gate
stage: design
gate: true
---

# API Contract Governor

Use this skill before implementation when API or service contracts are in scope.

## Position

Run after requirement/domain understanding and before technical design is treated as implementation-ready.

## Rules

- Generate `api_contract_design.json`; do not rely on prose-only API design.
- Name concrete API paths when known; block when a new/changed API is required but name, method, owner, or contract is ambiguous.
- Cover request parameters, response shape, error semantics, permission model, idempotency, pagination/filtering/sorting, compatibility, and consumer migration.
- Reused contracts must still be documented when they are part of the runtime sequence.

## Command

```bash
python3 scripts/api_contract.py \
  --spec artifacts/REQ-001/spec.json \
  --technical-design artifacts/REQ-001/technical_design.json \
  --out artifacts/REQ-001/api_contract_design.json
```

## Output

The script writes `codex-api-contract-design-v1` with `decision`, `contracts`, `compatibility`, `consumer_impact`, and `blockers`.
