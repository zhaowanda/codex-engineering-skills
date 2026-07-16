---
name: spec-governor
description: Normalize one-line requests, long PRDs, pasted notes, or imported requirement text into a structured spec artifact with scope, acceptance criteria, rules, risks, and open questions before technical design or coding.
category: workflow-gate
maturity: expert-gate
stage: requirements
gate: true
---

# Spec Governor

## Semantic Rules

- Consume structured Requirement IR sections before keyword inference.
- Treat explicit goals, nested acceptance criteria, entrypoints, constraints, and forbidden/reference paths as source-backed facts.
- Missing quantitative metrics are advisory unless the requirement explicitly makes a threshold release-critical.
- Emit one `scope_model` with `modify`, `reference_only`, `contract_confirm_only`, `forbidden`, and `unresolved` roles.
- Do not set `multi_repo_required=true` without at least two concrete repositories or an explicit cross-repo statement.

Use this skill before technical design, architecture design, delivery planning, or implementation.

## Command

```bash
python3 scripts/spec_governor.py \
  normalize \
  --doc-id REQ-001 \
  --title "Checkout discount display" \
  --input requirement.txt \
  --requirement-ir artifacts/REQ-001/requirement_ir.json \
  --project-understanding artifacts/project-understanding \
  --out artifacts/REQ-001/spec.json
```

Validate a spec:

```bash
python3 scripts/spec_governor.py \
  validate \
  --file artifacts/REQ-001/spec.json
```

## Rules

- Block design if requirement summary, acceptance criteria, scope, or actors are missing.
- Block design if the real business purpose, business flow, or triggering entrypoint cannot be understood or is only inferred from a vague action.
- Require an explicit business purpose/current pain point/expected business outcome; do not treat "optimize/support/fix/sync" as a real purpose.
- Separate confirmed facts, inferred assumptions, and unresolved points; never hide assumptions inside normalized requirements.
- Assign `requirements_understanding.level`: `expert_ready`, `clarification_required`, or `insufficient_context`.
- Block design when ambiguous terms such as "优化", "支持", "同步", "修复", "默认", "状态更新", "optimize", "support", "sync", or "fix" are not resolved into concrete behavior, scope, trigger, and acceptance evidence.
- Block implementation if open questions are not closed.
- Block design when extracted business rules conflict.
- Keep extracted facts separate from assumptions.
- For long PRDs, preserve business rules and source evidence references.
- Extract business objects, operations, data fields, state transitions, impact surface, implicit constraints, and negative acceptance needs.
- Extract business intent, current business problem, expected business outcome, business flow, entrypoints, trigger conditions, preconditions, postconditions, and ambiguity records.
- Model business flow as structured steps with actor, entrypoint, trigger, system actions, downstream effects, result, and branch signals.
- Capture current business state evidence when available: existing UI/API/task/MQ/manual entrypoints, existing data ownership, downstream dependencies, and whether the change reuses, modifies, or adds capability.
- Prefer `requirement_ir.json` hierarchy over flat line parsing so correction headings and acceptance subheadings cannot become executable requirements by accident.
- When `--project-understanding` contains `evidence_bundle.json`, consume only its confirmed modify/reference anchors and contracts; use legacy broad artifacts only as a compatibility fallback.
- Distinguish required, conditional, and excluded impacts. Runtime data is not database migration evidence, and an explicitly preserved API/field contract is not a change trigger.
- Treat broad code-index matches as candidates, not confirmed current-state facts.
- Use only `source_location_evidence.confirmed_anchors` as confirmed code entrypoints; block design when supplied source-location evidence has no confirmed anchor.
- Produce `evidence_match_table` with `evidence_match_score` and `match_reason` for project evidence used by current-state and dependency reasoning.
- Build `business_closure_model` from actor/external trigger through UI/API/task/consumer, domain behavior, DB/MQ/cache/downstream effects, and visible business result.
- Build `runtime_dependency_graph` with nodes/edges, `degree`, and `source_evidence` from dependency chain, closure model, and project evidence.
- Score `business_goal_quality` from explicit goal, target user, measurable metric, testable outcome, and flow binding.
- For stateful, asynchronous, retry, timeout, idempotency, compensation, MQ, or synchronization requirements, require `state_machine` with transitions, retry policy, idempotency key, timeout rule, compensation rule, invalid transitions, and completeness scoring when applicable.
- For multi-system or multi-repository requirements, extract `repo_impact_map` and `dependency_chain` with owner, upstream, downstream, and dependency order evidence.
- Score requirement understanding across intent, flow, entrypoint, acceptance, and evidence dimensions; `expert_ready` requires all core dimensions to meet the expert threshold.
- Convert high-risk implicit constraints into derived clarification questions and expert readiness gaps.
- Treat fully inferred acceptance criteria as usable but not expert-ready until confirmed.
- Do not accept weak acceptance criteria such as "功能正常", "页面展示正确", "数据同步成功", "状态更新正确", or "满足业务需求" without executable evidence rules.

## Output

The output uses schema `codex-spec-v1`.

Key fields:

- `business_intent`
- `business_problem`
- `expected_business_outcome`
- `business_flow`
- `business_flow_model`
- `business_closure_model`
- `entrypoints`
- `current_business_state`
- `current_state_evidence`
- `evidence_match_table`
- `project_evidence`
- `state_machine`
- `business_goal_quality`
- `repo_impact_map`
- `dependency_chain`
- `runtime_dependency_graph`
- `trigger_conditions`
- `ambiguities`
- `requirements_understanding`
- `requirements_understanding.scorecard`
- `requirements_understanding_evidence`
- `success_metrics`
- `confirmed_facts`
- `inferred_assumptions`
- `unresolved_points`
- `understanding_confidence`
- `design_allowed`
- `implementation_allowed`
- `impact_applicability`
- `requirement_ir`
