---
name: technical-design-governor
description: Generate a structured technical design draft from a normalized spec before implementation. Use when a requirement needs process flow, module decomposition, logical data flow, API contracts, UI/UX behavior, solution options, test strategy, and traceability.
---

# Technical Design Governor

Use this skill after `spec-governor` and before architecture design or delivery planning.

## Command

```bash
python3 skills/core/technical-design-governor/scripts/technical_design.py \
  --spec artifacts/REQ-001/spec.json \
  --out artifacts/REQ-001/technical_design.json
```

Then run `design-architecture-reviewer` after architecture design exists.

## Rules

- Generate concrete structure from spec facts.
- Preserve open questions; do not hide uncertainty.
- Include at least two solution options and a selected option.
- Include traceability from requirements to acceptance and tests.

## Output

The output uses schema `codex-technical-design-v1`.
