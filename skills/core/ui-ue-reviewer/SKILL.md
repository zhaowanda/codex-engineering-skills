---
name: ui-ue-reviewer
description: Review UI/UE design artifacts for expert-level interaction clarity before frontend implementation. Use after ui-ue-design-governor or when a technical design contains ui_ue_design for frontend-visible requirements.
category: reviewer
maturity: expert-gate
stage: design
gate: true
---

# UI/UE Reviewer

Use this skill to block shallow UI/UE designs before implementation.

## Position

Run after `ui-ue-design-governor` and before frontend implementation planning or delivery planning.

## Rules

- Review `ui_ue_design.json` first; fall back to `technical_design.json.ui_ue_design` only for legacy artifacts.
- A frontend requirement must name the real entry action, not only "existing entry".
- Require state coverage for loading, empty, success, validation error, permission denied, and dependency error unless explicitly waived.
- Require API/data/permission dependencies needed by the UI to be visible.
- Require acceptance evidence that can be executed through browser, component, screenshot, or accessibility checks.

## Command

```bash
python3 scripts/ui_ue_review.py \
  --ui-ue-design artifacts/REQ-001/ui_ue_design.json \
  --out artifacts/REQ-001/ui_ue_review.json
```

## Output

The script writes `codex-ui-ue-review-v1` with `decision`, `score`, `level`, `findings`, `blockers`, and `readiness_gate.frontend_implementation_allowed`.
