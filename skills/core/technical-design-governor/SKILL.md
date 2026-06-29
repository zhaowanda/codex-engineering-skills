---
name: technical-design-governor
description: Generate a structured technical design draft from a normalized spec before implementation. Use when a requirement needs process flow, module decomposition, logical data flow, API contracts, UI/UX behavior, solution options, test strategy, and traceability.
category: artifact-generator
maturity: deterministic-helper
stage: design
gate: false
---

# Technical Design Governor

Use this skill after `spec-governor` and before architecture design or delivery planning.

## Position

```text
spec-governor
-> technical-design-governor
-> architecture-design-governor
-> design-architecture-reviewer
```

## Command

```bash
python3 scripts/technical_design.py \
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

The artifact includes process flow, modules, logical data flow, API/UI behavior, options, selected approach, tests, risks, and traceability.
