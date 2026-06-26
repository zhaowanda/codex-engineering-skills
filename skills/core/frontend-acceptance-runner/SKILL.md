---
name: frontend-acceptance-runner
description: Generate and validate frontend browser acceptance evidence for UI changes. Use when a route, page, table, form, detail view, export flow, permission visibility, or browser interaction changed and release needs DOM, network, console, screenshot, and interaction evidence.
---

# Frontend Acceptance Runner

Use this skill after frontend implementation and before test evidence or release evidence binding.

## Position

```text
frontend implementation
-> frontend-acceptance-runner
-> test-evidence-gate
-> release-evidence-binder
```

## Scope

- Generate a `frontend_acceptance.json` template for browser evidence collection.
- Validate filled browser evidence from Chrome DevTools MCP, Playwright, Cypress, or manual browser runs.
- Block release when the evidence is thin, failed, or missing critical UI behavior.

## Page Types

- `list`: filters, table columns, pagination, empty state, row actions.
- `form`: field defaults, validation, submit, success/failure state.
- `detail`: key fields, status, related data, actions.
- `export`: export trigger, download/output, row count or file evidence.
- `dashboard`: charts/cards, loading state, data refresh, responsive behavior.
- `custom`: use explicit checks in `custom_checks`.

## Commands

Create a template:

```bash
python3 scripts/frontend_acceptance.py \
  template \
  --page-type list \
  --target-url http://localhost:3000/orders \
  --artifact-dir artifacts/review
```

Validate evidence:

```bash
python3 scripts/frontend_acceptance.py \
  validate \
  --file artifacts/review/frontend_acceptance.json
```

## Evidence Rules

- `pass=true` requires page load evidence and at least one DOM, screenshot, or interaction proof.
- Console errors block pass.
- Failed network requests block pass unless explicitly waived with a reason.
- `form` pages require validation and submit evidence.
- `export` pages require export output evidence.
- Permission-sensitive pages require role/visibility checks.
- Responsive-required pages require viewport evidence.

## Output

The output uses schema `codex-frontend-acceptance-v1`.

Decision values:

- `pass`
- `block`
