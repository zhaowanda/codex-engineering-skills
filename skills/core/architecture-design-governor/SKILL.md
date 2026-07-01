---
name: architecture-design-governor
description: Generate a structured architecture design draft from normalized spec and technical design before delivery planning. Use when a requirement needs component boundaries, repo responsibilities, cross-repo contracts, data ownership, integration sequence, deployment, rollback, and architecture option comparison.
category: artifact-generator
maturity: deterministic-helper
stage: design
gate: false
---

# Architecture Design Governor

Use this skill after technical design and before delivery plan.

## Position

```text
technical-design-governor
-> architecture-design-governor
-> design-architecture-reviewer
-> delivery-plan-templates
```

## Command

```bash
python3 scripts/architecture_design.py \
  --spec artifacts/REQ-001/spec.json \
  --technical-design artifacts/REQ-001/technical_design.json \
  --out artifacts/REQ-001/architecture_design.json
```

## Rules

- Include at least two architecture options.
- Prefer real repo entrypoints, module paths, routes, and dependency direction from project-understanding artifacts.
- Fallback architecture phrases such as `existing producer` or `target owner` must remain visible as uncertainty and should not pass expert review.
- Mark repo responsibilities as `modify`, `confirm_only`, `read_only`, or `out_of_scope`.
- Separate data ownership from data flow.
- Include deployment, rollback, observability, and risk sections.

## Output

The output uses schema `codex-architecture-design-v1`.

The artifact contains architecture options, selected option, repository responsibilities, contracts, data ownership, deployment, rollback, observability, and risks.
