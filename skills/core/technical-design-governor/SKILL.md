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
- Decision contract: this generator must emit enough structured evidence for `design-architecture-reviewer` to return `decision=pass`; otherwise downstream implementation must stay blocked.
- Requirement understanding gate: carry `requirements_understanding`, `requirements_understanding_gate`, `business_intent`, `business_flow`, `business_flow_model`, `business_closure_model`, `entrypoints`, `current_business_state`, `current_state_evidence`, `evidence_match_table`, `state_machine`, `business_goal_quality`, `repo_impact_map`, `dependency_chain`, and `runtime_dependency_graph` from `spec-governor` into the technical design. If `spec.design_allowed=false`, set design confidence low, mark the checklist blocked, preserve blockers/ambiguities, and do not present the design as implementation-ready.
- Failure path: if current behavior, owner entrypoint, API contract, data model, runtime sequence, test mapping, or option comparison cannot be grounded in requirement/project evidence, keep that uncertainty explicit and require review revision instead of presenting a guessed design as ready.
- When project-understanding artifacts are available, populate current-state analysis, code entrypoints, modules, routes, tests, and compatibility notes from real repository facts.
- Do not present fallback phrases such as `target module to be confirmed` as expert-ready facts; keep them as review-blocking uncertainty.
- Preserve open questions; do not hide uncertainty.
- Include at least two solution options and a selected option.
- Explain each option before selecting a solution; do not place the decision ahead of option detail and comparison.
- For every solution option, include when to choose it, implementation outline, risk controls, test evidence, rollout impact, performance impact, and rollback strategy.
- Include a weighted option comparison matrix, score summary, decision confidence, implementation invariants, and expert review checklist.
- When relevant, include data model/table schema changes, multi-system interaction sequence, MQ upstream/downstream trigger rules, cache strategy, transaction consistency, and observability design.
- Include traceability from requirements to acceptance and tests.

## Output

The output uses schema `codex-technical-design-v1`.

The artifact includes process flow, modules, logical data flow, API/UI behavior, data model/table schema, system sequence, MQ/cache/transaction/observability decisions, detailed options, selected approach, weighted comparison matrix, score summary, invariants, tests, risks, and traceability.

Readiness decision is enforced by `design-architecture-reviewer`: missing or weak design evidence must appear as review findings/blockers and must not proceed to implementation until the review decision is pass.
