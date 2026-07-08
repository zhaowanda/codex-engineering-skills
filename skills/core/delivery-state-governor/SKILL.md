---
name: delivery-state-governor
description: Maintain one canonical delivery_state.json for AI-assisted engineering workflows. Use to initialize, inspect, advance, block, unblock, and validate requirement stage state across requirement docs, design, Git, implementation, review, test, release, and post-release gates.
category: workflow-gate
maturity: expert-gate
stage: delivery-planning
gate: true
---

# Delivery State Governor

Use this skill as the single machine-readable status board for a requirement. It does not replace detailed artifacts; it records which stage is current, which gates are required, which evidence exists, and why delivery is blocked.

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
- Do not implement unless `validate --target implementation` returns `decision=ready`.
- Do not release unless `validate --target release` returns `decision=ready`.
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
