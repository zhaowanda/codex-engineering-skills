---
name: cross-repo-planner
description: Generate and validate a cross-repository execution graph for multi-repo requirements. Use after spec normalization and before delivery planning when a change spans provider/consumer APIs, frontend-backend flows, shared dependencies, configuration, database changes, or coordinated release order.
category: artifact-generator
maturity: deterministic-helper
stage: delivery-planning
gate: false
---

# Cross Repo Planner

Use this skill when one requirement touches more than one repository or has cross-repository contract risk.

## Position

```text
canonical spec + project registry + optional delivery_plan
-> cross-repo-planner
-> cross_repo_readiness gate
-> repo delivery plans / git worktree preparation
-> integration and release gates
```

## Rules

- Generate `cross_repo_execution_graph.json` before parallel implementation.
- Treat provider repositories as upstream of consumers when dependencies or contract hints exist.
- Mark API, event, schema, shared dependency, database, permission, and configuration changes as contract freeze points.
- Split work into `parallel_safe`, `contract_blocked`, and `serial_required` groups.
- Block dependency cycles and unknown registry repositories.
- For single-repository inputs, emit `applicable=false` with a passing readiness/release decision and a not-applicable reason; do not block implementation merely because the cross-repo gate was invoked by a broad profile.
- Treat missing per-repo delivery tasks as readiness blockers even when the graph shape can be generated.
- Require per-repo edit permits before implementation; require integration evidence before release.
- Keep project-specific details in private overlays; open-core replay cases must be anonymized.
- Do not treat a graph as implementation permission. It only proves parallelization shape and blockers.

## Commands

Generate example artifacts:

```bash
python3 scripts/cross_repo_plan.py \
  plan \
  --example \
  --out-dir /tmp/cross-repo-plan
```

Generate from project registry:

```bash
python3 scripts/cross_repo_plan.py \
  plan \
  --doc-id REQ-001 \
  --spec artifacts/spec.json \
  --registry overlay/projects.yaml \
  --delivery-plan artifacts/delivery_plan.json \
  --out-dir artifacts/cross_repo
```

Validate a graph:

```bash
python3 scripts/cross_repo_plan.py \
  validate \
  --graph artifacts/cross_repo/cross_repo_execution_graph.json
```

## Output

The output uses:

- `codex-cross-repo-execution-graph-v1`
- `codex-cross-repo-readiness-v1`
- `codex-cross-repo-release-plan-v1`
- `codex-cross-repo-graph-validation-v1`

The graph reports repositories, dependency edges, parallel groups, contract freeze points, integration gates, blockers, and a `decision` of `ready` or `blocked`.
