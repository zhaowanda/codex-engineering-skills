---
name: architecture-design-governor
description: Generate a structured architecture design draft from normalized spec and technical design before delivery planning. Use when a requirement needs component boundaries, repo responsibilities, cross-repo contracts, data ownership, integration sequence, deployment, rollback, and architecture option comparison.
category: artifact-generator
maturity: deterministic-helper
stage: design
gate: false
---

# Architecture Design Governor

Use this skill after pre-technical architecture framing and detailed technical design; use it to refine, validate, and correct boundaries before delivery planning.

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
  --architecture-framing artifacts/REQ-001/architecture_framing.json \
  --out artifacts/REQ-001/architecture_design.json
```

## Rules

- Decision contract: this generator must emit enough ownership, dependency, deployment, rollback, and option evidence for `design-architecture-reviewer` to return `decision=pass`; otherwise delivery planning and implementation must remain blocked.
- Refine `architecture_framing.json` rather than replacing it. If technical design violates the framed owner, provider/consumer, data ownership, release, or rollback boundary, record that as an architecture risk or review blocker.
- Requirement understanding gate: propagate the technical/spec `requirements_understanding_gate`, including `business_closure_model`, `state_machine`, `business_goal_quality`, `repo_impact_map`, `dependency_chain`, and `runtime_dependency_graph`, into architecture design. If `design_allowed=false`, architecture confidence must be low, architecture checklist must be blocked, and delivery planning must wait for requirement clarification.
- Failure path: if owner repo, integration direction, contract compatibility, data ownership, release order, rollback, or new-service justification cannot be grounded in requirement/project evidence, keep the uncertainty explicit and require review revision instead of presenting a guessed architecture as ready.
- Include at least two architecture options.
- Explain each architecture option before selecting one; do not place the architecture decision ahead of option detail and comparison.
- Prefer real repo entrypoints, module paths, routes, and dependency direction from project-understanding artifacts.
- Fallback architecture phrases such as `existing producer` or `target owner` must remain visible as uncertainty and should not pass expert review.
- Mark repo responsibilities as `modify`, `confirm_only`, `read_only`, or `out_of_scope`.
- Separate data ownership from data flow.
- For every architecture option, include when to choose it, owner/confirm-only repos, integration impact, deployment impact, rollback complexity, risk controls, validation, and performance impact.
- Include a weighted architecture fit matrix, score summary, decision confidence, architecture invariants, and expert review checklist.
- Include deployment, rollback, observability, and risk sections.

## Output

The output uses schema `codex-architecture-design-v1`.

The artifact emits top-level `decision` and `blockers`; downstream workflow contracts accept only `decision=pass`.

The artifact contains detailed architecture options, selected option, weighted fit matrix, score summary, repository responsibilities, contracts, invariants, data ownership, deployment, rollback, observability, and risks.

Readiness decision is enforced by `design-architecture-reviewer`: missing ownership, contract, deployment, rollback, or new-service evidence must appear as review findings/blockers and must not proceed to delivery planning or implementation until the review decision is pass.
