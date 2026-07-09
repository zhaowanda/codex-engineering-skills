---
name: design-architecture-reviewer
description: Review technical design and architecture design artifacts before delivery planning or implementation. Use to score design depth, requirement coverage, process flow, data flow, module boundaries, API contracts, UI/UX behavior, option comparison, security, performance, cohesion/coupling, rollback, observability, and testability.
category: workflow-gate
maturity: expert-gate
stage: design
gate: true
---

# Design Architecture Reviewer

Use this skill after technical and architecture design are drafted, before delivery plan freeze or implementation.

## Position

```text
spec
-> technical_design
-> architecture_design
-> design-architecture-reviewer
-> delivery_plan
-> git / edit gates
-> implementation
```

## Rules

- Do not allow implementation when this review returns `decision=block`.
- Do not allow implementation when `readiness_gate.implementation_allowed=false`.
- A design is not expert-ready unless requirements trace to process flow, modules, data flow, API/UI impact, tests, acceptance evidence, and selected options.
- Require at least two technical solution options and two architecture options unless a documented waiver exists.
- Require each technical and architecture option to include applicability, execution outline or integration/deployment impact, risk controls, validation, performance impact, and rollback detail.
- Require weighted comparison matrices and score summaries so selected and rejected options are visibly comparable.
- Require explicit selected option, decision criteria, tradeoffs, and rejected alternative reasoning.
- Require current-state analysis with concrete code entrypoints, interface examples for API changes, compatibility matrix, dependency graph, failure isolation, and deployment impact matrix when relevant.
- Require data model/table schema detail when data changes are signaled.
- Require multi-system sequence, timeout/retry, idempotency, and consistency handling when API/cross-system interaction is signaled.
- Require MQ producer, consumer, topic/queue, trigger timing, payload, idempotency key, retry policy, and dead-letter/compensation when asynchronous messaging is signaled.
- Require cache key, value shape, TTL, invalidation, and consistency-risk decision when cache is chosen.
- Require transaction boundary, idempotency, compensation, and rollback when consistency or multi-write risk is signaled.
- Require security, performance, rollback, observability, and test strategy to be executable, not generic.
- Treat placeholders such as `TBD`, `unknown`, `todo`, and `confirm later` as findings unless they are inside an explicitly controlled gate.

## Commands

Review:

```bash
python3 scripts/design_arch_review.py \
  review \
  --technical-design artifacts/technical_design.json \
  --architecture-design artifacts/architecture_design.json \
  --out artifacts/design_architecture_review.json
```

Validate a review artifact:

```bash
python3 scripts/design_arch_review.py \
  validate \
  --file artifacts/design_architecture_review.json
```

## Minimum Technical Design Shape

The reviewer expects these sections when relevant:

- `design_scope`
- `requirement_trace`
- `business_rule_mapping`
- `process_flow`
- `module_decomposition`
- `logical_data_flow`
- `target_behavior`
- `api_contracts`
- `data_design`
- `data_model_design`
- `table_schema_changes`
- `system_interaction_sequence`
- `mq_interactions`
- `cache_strategy`
- `transaction_consistency`
- `observability_design`
- `permission_model`
- `compatibility_strategy`
- `exception_and_edge_cases`
- `non_functional_requirements`
- `solution_options`
- `selected_solution`
- `design_traceability_matrix`
- `acceptance_mapping`
- `ui_ue_design`
- `test_strategy`

## Minimum Architecture Design Shape

The reviewer expects these sections when relevant:

- `architecture_scope`
- `architecture_options`
- `selected_architecture`
- `architecture_traceability_matrix`
- `component_boundaries`
- `module_topology`
- `repo_responsibilities`
- `cross_repo_contracts`
- `data_flow`
- `data_ownership`
- `integration_sequence`
- `security_and_permission`
- `observability`
- `monitoring_alerts`
- `deployment_topology`
- `deployment_impact`
- `migration_strategy`
- `gray_release_strategy`
- `rollback_strategy`
- `decision_records`

## Output

The review output uses schema `codex-design-architecture-review-v1` and includes:

- `score`: 0-100.
- `level`: `expert_ready`, `reviewable`, `needs_revision`, or `block`.
- `decision`: `pass`, `needs_revision`, or `block`.
- `readiness_gate.implementation_allowed`: true only when decision is pass, score is at least 85, and no blocker/high/medium findings exist.
- grouped findings by review area.
