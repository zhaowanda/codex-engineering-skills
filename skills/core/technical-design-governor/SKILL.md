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
- When project-understanding artifacts are available, populate current-state analysis, code entrypoints, modules, routes, tests, and compatibility notes from real repository facts.
- Do not present fallback phrases such as `target module to be confirmed` as expert-ready facts; keep them as review-blocking uncertainty.
- Preserve open questions; do not hide uncertainty.
- Include at least two solution options and a selected option.
- For every solution option, include when to choose it, implementation outline, risk controls, test evidence, rollout impact, performance impact, and rollback strategy.
- Include a weighted option comparison matrix, score summary, decision confidence, implementation invariants, and expert review checklist.
- When relevant, include data model/table schema changes, multi-system interaction sequence, MQ upstream/downstream trigger rules, cache strategy, transaction consistency, and observability design.
- Include traceability from requirements to acceptance and tests.

## Output

The output uses schema `codex-technical-design-v1`.

The artifact includes process flow, modules, logical data flow, API/UI behavior, data model/table schema, system sequence, MQ/cache/transaction/observability decisions, detailed options, selected approach, weighted comparison matrix, score summary, invariants, tests, risks, and traceability.
