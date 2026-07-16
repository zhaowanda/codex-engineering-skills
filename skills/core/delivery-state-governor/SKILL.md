---
name: delivery-state-governor
description: Maintain a compatibility navigation snapshot in delivery_state.json. Use to initialize, inspect, advance, block, unblock, and validate legacy delivery state while workflow-stages-v4 and delivery-runner remain the canonical readiness authority.
category: artifact-generator
maturity: deterministic-helper
stage: delivery-planning
gate: false
---

# Delivery State Governor

Use this skill as a legacy-compatible navigation snapshot for a requirement. It does not replace detailed artifacts or the canonical stage registry.

## Authority

- `config/workflow-stages.example.yaml` and `delivery-runner` are the only implementation/release readiness authority.
- `delivery_state.json` may summarize progress for existing integrations, but it cannot grant implementation or release permission.
- A state validation result is advisory unless the same evidence also passes the v3 artifact contracts, dependency checks, and lineage checks.

## Position

```text
stable doc_id
-> delivery-state-governor init
-> every gate imports or advances state
-> implementation/release checks state before proceeding
```

## Commands

Initialize:

```bash
python3 scripts/delivery_state.py \
  init \
  --doc-id REQ-20260623-example \
  --lane standard_requirement \
  --repo web-app \
  --repo api-service \
  --artifact-dir /path/to/artifacts
```

Advance:

```bash
python3 scripts/delivery_state.py \
  advance \
  --state /path/to/artifacts/delivery_state.json \
  --stage technical_design \
  --gate technical_design \
  --evidence /path/to/technical_design.json
```

Block:

```bash
python3 scripts/delivery_state.py \
  block \
  --state /path/to/artifacts/delivery_state.json \
  --reason "open clarification questions remain" \
  --next-action "answer clarification records and rerun spec"
```

Validate before implementation or release:

```bash
python3 scripts/delivery_state.py \
  validate \
  --state /path/to/artifacts/delivery_state.json \
  --target implementation
```

## Rules

- Create state as soon as a stable `doc_id` exists.
- Treat `delivery_state.json` as navigation state, not the source of detailed facts.
- Store detailed facts in spec/design/plan/test/release/evidence artifacts.
- Every blocker must have a concrete next action.
- Do not use `validate --target implementation` or `validate --target release` as a substitute for `delivery-runner` readiness.
- When repo states declare `requires_git` or `requires_edit_permit`, validation requires matching per-repo evidence before implementation.
- Release validation blocks incomplete `integration_gates` unless each gate is `passed`, `ready`, `complete`, or `waived`.
- Let downstream gates advance only the evidence they own.
- Keep chat output small; point to evidence paths.

## Output

```json
{
  "schema": "codex-delivery-state-v1",
  "doc_id": "",
  "lane": "",
  "current_stage": "",
  "status": "draft | blocked | ready | in_progress | closed",
  "required_gates": [],
  "passed_gates": [],
  "evidence": {},
  "repo_states": [],
  "integration_gates": [],
  "blockers": [],
  "next_action": "",
  "history": []
}
```

## Lanes

- `hotfix`: production incident, shortest safe path, retrofit evidence after fix.
- `bugfix`: ordinary defect, requires reproduction, Git, implementation, review, tests, release evidence.
- `small_change`: low-risk field/text/display change, requires light design and focused validation.
- `standard_requirement`: normal feature/change, requires full spec/design/plan/git/review/test/release flow.
- `large_prd`: long PRD or multi-repo work, requires ingestion, full design, QA traceability, UAT, and post-release observation.
- `migration`: platformization or data/config/provider migration, requires current baseline, target architecture, compatibility, dual-run, rollback, and integration/UAT evidence.
- `review_only`: review without implementation.
- `docs_reverse`: reconstruct baseline docs from existing code.
