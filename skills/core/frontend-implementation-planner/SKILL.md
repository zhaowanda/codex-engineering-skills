---
name: frontend-implementation-planner
description: Map UI/UE design into concrete frontend implementation work. Use after UI/UE design for frontend routes, components, state handling, API calls, permissions, and browser acceptance planning.
category: artifact-generator
maturity: expert-gate
stage: delivery-planning
gate: true
---

# Frontend Implementation Planner

Use this skill after `ui-ue-design-governor` and before delivery planning for frontend-visible requirements.

## Position

Run after UI/UE review and before delivery-plan generation so frontend work is mapped to concrete files and evidence.

## Rules

- Plan concrete frontend files, routes, components, API calls, permission checks, state handling, and evidence.
- Keep implementation aligned with existing design-system components and repository conventions.
- Do not treat frontend hiding as authorization; server-side permission remains authoritative.
- If route/component/API ownership is unclear, block implementation planning and require project understanding.

## Command

```bash
python3 scripts/frontend_plan.py \
  --ui-ue-design artifacts/REQ-001/ui_ue_design.json \
  --technical-design artifacts/REQ-001/technical_design.json \
  --out artifacts/REQ-001/frontend_implementation_plan.json
```

## Output

The script writes `codex-frontend-implementation-plan-v1` with routes, component work, state handling, API dependencies, permission handling, and acceptance evidence.
