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
-> applicable UI/API/data/observability/configuration/security/performance reviews
-> design-architecture-reviewer
-> delivery_plan
-> cross-repo readiness when applicable
-> final design-architecture-reviewer refresh when cross-repo readiness is produced
-> git / edit gates
-> implementation
```

## Rules

- Do not allow implementation when this review returns `decision=block`.
- Do not allow implementation when `readiness_gate.implementation_allowed=false`.
- Block designs whose technical or architecture artifact carries `requirements_understanding_gate.design_allowed=false`; requirements must have explicit business intent, concrete business flow, entrypoints/triggers, and acceptance evidence before implementation.
- A design is not expert-ready unless requirements trace to process flow, modules, data flow, API/UI impact, tests, acceptance evidence, and selected options.
- Require at least two technical solution options and two architecture options unless a documented waiver exists.
- Require each technical and architecture option to include applicability, execution outline or integration/deployment impact, risk controls, validation, performance impact, and rollback detail.
- Require weighted comparison matrices and score summaries so selected and rejected options are visibly comparable.
- Require explicit selected option, decision criteria, tradeoffs, and rejected alternative reasoning.
- Require current-state analysis with concrete code entrypoints, interface examples for API changes, compatibility matrix, dependency graph, failure isolation, and deployment impact matrix when relevant.
- When source-location evidence exists, block selected entrypoints and implementation modules outside `confirmed_anchors`.
- Block rejected candidates that leak into modules, selected options, deployment, rollback, or implementation scope.
- Also block rejected candidates in process flow, current-state analysis, logical data flow, API contracts, and system interaction sequences.
- Require a multi-step business flow when multiple acceptance mappings describe an ordered user/system workflow.
- Require `process_flow_diagram` as Mermaid `flowchart` whenever `process_flow` is present, and block when the diagram omits reviewed actors or actions.
- Do not accept manually asserted high entrypoint confidence without direct source confirmation.
- Require data model/table schema detail when data changes are signaled.
- Require multi-system sequence, timeout/retry, idempotency, and consistency handling when API/cross-system interaction is signaled.
- Require Mermaid `system_sequence_diagram` and `integration_sequence_diagram` whenever structured system or integration sequences apply; diagrams must stay aligned with the reviewed sequence participants and actions.
- Require MQ producer, consumer, topic/queue, trigger timing, payload, idempotency key, retry policy, and dead-letter/compensation when asynchronous messaging is signaled.
- Require cache key, value shape, TTL, invalidation, and consistency-risk decision when cache is chosen.
- Require transaction boundary, idempotency, compensation, and rollback when consistency or multi-write risk is signaled.
- Require `new_service_design` when a requirement creates a new service, repository, or project. It must explain why existing systems cannot own the change and define responsibility boundaries, bootstrap, module structure, API contracts, CI/CD, configuration, deployment, observability, security, maintenance ownership, rollout/migration, and rollback.
- Require security, performance, rollback, observability, and test strategy to be executable, not generic.
- Treat placeholders such as `TBD`, `unknown`, `todo`, and `confirm later` as findings unless they are inside an explicitly controlled gate.
- Consume every applicable specialty artifact rather than treating it as advisory prose: UI/UE review, API contract design, data model design, observability design, configuration readiness, data security review, performance review, and cross-repo readiness.
- Promote blocking specialty decisions or blockers into the total-design blockers. The aggregate review cannot pass while an applicable specialty gate is unresolved.
- Record `input_digests` for technical design, architecture design, and every supplied specialty artifact so orchestration can detect a stale aggregate review.
- When cross-repo readiness is produced after the first delivery plan, rerun the aggregate review and then refresh downstream plan/traceability evidence as needed before implementation.

## Commands

Review:

```bash
python3 scripts/design_arch_review.py \
  review \
  --technical-design artifacts/technical_design.json \
  --architecture-design artifacts/architecture_design.json \
  --ui-ue-review artifacts/ui_ue_review.json \
  --api-contract-design artifacts/api_contract_design.json \
  --data-model-design artifacts/data_model_design.json \
  --observability-design artifacts/observability_design.json \
  --configuration-readiness artifacts/configuration_readiness.json \
  --data-security-review artifacts/data_security_review.json \
  --performance-review artifacts/performance_review.json \
  --cross-repo-readiness artifacts/cross_repo_readiness.json \
  --out artifacts/design_architecture_review.json
```

Pass only the specialty artifacts that apply to the selected workflow profile and impact set.

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
- `new_service_design` when creating a new service/repository/project
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
- `specialty_review_summary`: decision and blocker summary for each supplied specialty artifact.
- `input_digests`: content digests used by orchestration to invalidate stale reviews.
- grouped findings by review area.
