---
name: technical-design-governor
description: Generate a structured technical design draft from a normalized spec before implementation. Use when a requirement needs process flow, module decomposition, logical data flow, API contracts, UI/UX behavior, solution options, test strategy, and traceability.
category: artifact-generator
maturity: deterministic-helper
stage: design
gate: false
---

# Technical Design Governor

Generate process and sequence models from confirmed entrypoints, source anchors, contracts, states, and acceptance branches. Do not create a process diagram by serializing acceptance text. Every sequence edge must name participants, action, success, failure, state transition, and source evidence.

Use this skill after requirement/domain understanding, architecture framing, and applicable UI/API/data/observability specialty design; run it before architecture refinement or delivery planning.

## Position

```text
spec-governor
-> domain-model-governor
-> architecture-framing-governor
-> specialty design governors
-> technical-design-governor
-> architecture-design-governor
-> design-architecture-reviewer
```

## Command

```bash
python3 scripts/technical_design.py \
  --spec artifacts/REQ-001/spec.json \
  --architecture-framing artifacts/REQ-001/architecture_framing.json \
  --out artifacts/REQ-001/technical_design.json
```

Then run `design-architecture-reviewer` after architecture design exists.

## Rules

- Generate concrete structure from spec facts.
- Decision contract: this generator must emit enough structured evidence for `design-architecture-reviewer` to return `decision=pass`; otherwise downstream implementation must stay blocked.
- Requirement understanding gate: carry `requirements_understanding`, `requirements_understanding_gate`, `business_intent`, `business_flow`, `business_flow_model`, `business_closure_model`, `entrypoints`, `current_business_state`, `current_state_evidence`, `evidence_match_table`, `state_machine`, `business_goal_quality`, `repo_impact_map`, `dependency_chain`, and `runtime_dependency_graph` from `spec-governor` into the technical design. If `spec.design_allowed=false`, set design confidence low, mark the checklist blocked, preserve blockers/ambiguities, and do not present the design as implementation-ready.
- Failure path: if current behavior, owner entrypoint, API contract, data model, runtime sequence, test mapping, or option comparison cannot be grounded in requirement/project evidence, keep that uncertainty explicit and require review revision instead of presenting a guessed design as ready.
- When project-understanding artifacts are available, populate current-state analysis, code entrypoints, modules, routes, tests, and compatibility notes from real repository facts.
- When source-location evidence exists, select owner modules only from `confirmed_anchors` and block when none are confirmed.
- Never promote `rejected_candidates` or broad repository-index hints into implementation modules.
- Build `process_flow` as one ordered business flow from confirmed triggers, system actions, and observable acceptance outcomes; do not turn document headings or correction notes into standalone flows.
- Emit `process_flow_diagram` as a Mermaid `flowchart` derived from the reviewed `process_flow`; the diagram must stay semantically aligned with the structured steps.
- Prefer `source_location_evidence.confirmed_contracts` for API contracts and system interaction sequence participants.
- Emit `system_sequence_diagram` as a Mermaid `sequenceDiagram` derived from `system_interaction_sequence`; keep participants and actions consistent with the structured sequence rows.
- Do not present fallback phrases such as `target module to be confirmed` as expert-ready facts; keep them as review-blocking uncertainty.
- Preserve open questions; do not hide uncertainty.
- Include at least two solution options and a selected option.
- Explain each option before selecting a solution; do not place the decision ahead of option detail and comparison.
- For every solution option, include when to choose it, implementation outline, risk controls, test evidence, rollout impact, performance impact, and rollback strategy.
- Include a weighted option comparison matrix, score summary, decision confidence, implementation invariants, and expert review checklist.
- When relevant, include data model/table schema changes, multi-system interaction sequence, MQ upstream/downstream trigger rules, cache strategy, transaction consistency, and observability design.
- Consume `architecture_framing.json`, `ui_ue_design.json`, `api_contract_design.json`, `data_model_design.json`, `domain_model_design.json`, and `observability_design.json` when present; do not re-guess their owner, entrypoint, contract, data, or observability decisions.
- Include traceability from requirements to acceptance and tests.

## Output

The output uses schema `codex-technical-design-v1`.

The artifact includes process flow, `process_flow_diagram`, modules, logical data flow, API/UI behavior, data model/table schema, system sequence, `system_sequence_diagram`, MQ/cache/transaction/observability decisions, detailed options, selected approach, weighted comparison matrix, score summary, invariants, tests, risks, and traceability.

It also emits top-level `decision` and `blockers`; downstream workflow contracts accept only `decision=pass`.

Readiness decision is enforced by `design-architecture-reviewer`: missing or weak design evidence must appear as review findings/blockers and must not proceed to implementation until the review decision is pass.
