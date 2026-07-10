---
name: architecture-framing-governor
description: Generate pre-technical architecture framing for owner system, repository boundary, new-service decision, provider/consumer direction, data ownership, runtime entrypoints, dependency degree, release order, and rollback boundary. Use after requirement/domain understanding and before detailed technical design for standard, frontend, API, data, cross-repo, MQ, scheduled task, manual task, or new-service requirements.
category: artifact-generator
maturity: expert-gate
stage: design
gate: true
---

# Architecture Framing Governor

Use this skill before detailed technical design when system ownership or dependency direction can affect implementation.

## Position

Run after `spec-governor` and `domain-model-governor`; run before `technical-design-governor`.

```text
spec-governor
-> domain-model-governor
-> architecture-framing-governor
-> UI/API/data/observability specialty design
-> technical-design-governor
-> architecture-design-governor
```

## Command

```bash
python3 scripts/architecture_framing.py \
  --spec artifacts/REQ-001/spec.json \
  --domain-model-design artifacts/REQ-001/domain_model_design.json \
  --project-understanding artifacts/REQ-001/project_understanding \
  --out artifacts/REQ-001/architecture_framing.json
```

## Rules

- Decide architecture boundaries before implementation mechanics.
- State whether the requirement should modify existing systems or create a new service/repository.
- Classify repositories as `modify`, `confirm_only`, `read_only`, or `out_of_scope`.
- Identify runtime entrypoints: frontend action, API, scheduled task, MQ consumer, manual task, or existing reused contract.
- Record provider/consumer direction for APIs, MQ, cache, and downstream dependencies.
- Record dependency degree: direct owner only, one-degree dependency, or multi-degree chain.
- Name data owner and write authority when data is in scope; block if data ownership is ambiguous.
- For new-service signals, require creation reason, rejected existing owners, bootstrap baseline, deployment, and rollback boundary.
- Do not invent repository names, services, APIs, topics, or tables. Use `needs_confirmation` with blockers when evidence is missing.

## Output

The script writes `codex-architecture-framing-v1`:

- `decision`: `pass` when framing is actionable, `block` when boundary clarification is required.
- `system_boundary`: owner repo/system, decision type, new-service decision.
- `repo_responsibilities`: modify/confirm/read-only/out-of-scope boundaries.
- `runtime_entrypoints`: concrete entrypoint kinds and triggers.
- `dependency_graph`: provider/consumer edges and dependency degree.
- `data_ownership`: business object owner and write authority.
- `release_order` and `rollback_boundary`.
- `blockers` for ambiguous ownership, new-service, data, or dependency direction.
