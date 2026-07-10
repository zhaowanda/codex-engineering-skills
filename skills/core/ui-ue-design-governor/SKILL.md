---
name: ui-ue-design-governor
description: Generate expert UI/UE design artifacts before technical design. Use when a requirement affects frontend pages, menus, buttons, forms, tables, routes, dashboards, browser workflows, or user-visible interaction states.
category: artifact-generator
maturity: expert-gate
stage: design
gate: true
---

# UI/UE Design Governor

Use this skill after `spec-governor` and before `technical-design-governor` for any user-visible frontend change.

## Rules

- Generate `ui_ue_design.json`; do not bury UI/UE decisions only inside `technical_design.json`.
- Treat UI/UE as a product interaction contract: user goal, entry path, information architecture, interaction flow, state matrix, permission visibility, copy/i18n, responsive behavior, accessibility, and evidence.
- Anchor entrypoints in concrete business actions such as menu clicks, buttons, table actions, form submissions, tabs, dialogs, browser route loads, or periodic UI refreshes.
- If the UI goal, entrypoint, or business flow is ambiguous, return `decision: block` with clarification questions instead of inventing UX.
- Existing design systems and components are preferred. New UI patterns require a reason and acceptance evidence.
- Acceptance must be testable through browser, component, or screenshot evidence.

## Command

```bash
python3 scripts/ui_ue_design.py \
  --spec artifacts/REQ-001/spec.json \
  --technical-design artifacts/REQ-001/technical_design.json \
  --out artifacts/REQ-001/ui_ue_design.json
```

## Output

The script writes `codex-ui-ue-design-v1`:

- `decision`: `pass` when UI/UE is actionable, `block` when clarification is required, `not_applicable` when no UI impact exists.
- `experience_summary`: user, goal, entry surface, trigger action, business outcome.
- `screens`: routes/pages, information architecture, layout zones, component mapping.
- `interaction_flows`: ordered user actions and system responses.
- `state_matrix`: loading, empty, success, validation error, permission denied, dependency error, disabled, optimistic/progress states.
- `frontend_contract`: API/data dependencies needed by the UI.
- `acceptance_evidence`: browser, component, screenshot, accessibility, and visual regression evidence.
