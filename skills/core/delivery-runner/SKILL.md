---
name: delivery-runner
description: Inspect a delivery artifact folder and report current workflow stage, blockers, next command, and whether implementation or release is allowed. Use as the one-command entrypoint after spec/design/plan/git/review/test/release artifacts exist or when the user asks where the process is.
category: template-runner
maturity: orchestrator
stage: delivery-planning
gate: false
---

# Delivery Runner

Use this skill as the workflow status entrypoint.

## Command

```bash
python3 scripts/delivery_runner.py \
  inspect \
  --artifact-dir artifacts/REQ-001 \
  --profile small_feature
```

## Rules

- Prefer `delivery_state.json` when present.
- Also inspect key artifacts directly so users can see missing files.
- Evaluate the lifecycle registry in `config/workflow-stages.example.yaml` using schema `codex-workflow-stages-v4`, its Runtime gates, phase order, semantic dependencies, profile-selected skills, and detected impacts.
- Reject vacuous evidence even when schema and decision are valid by enforcing `evidence_fields`, typed constraints, cardinality, constants, patterns, and cross-field rules.
- Require lineage v2 semantic artifact digests, producer/command provenance, and fresh deterministic input digests.
- Verify Runtime session/checkpoint contracts as normal DAG stages. Historical checkpoint roots remain valid when present in the append-only event chain; later events must not invalidate earlier checkpoint business-evidence lineage.
- Fail closed unless every applicable artifact has the registered schema, required fields, accepted decision, empty blockers, and current input digests.
- Apply `conditional_skill` stages only when the selected profile requires that skill, and `conditional_impacts` stages only when the artifact set signals a matching impact.
- Block on dependency violations, including an artifact that exists while an applicable prerequisite is missing or not accepted.
- Compare recorded `input_digests` with every declared stage input; recursively block downstream artifacts when any input is stale, removed, or replaced.
- Validate profile digest bindings such as `open_questions.json.spec_digest` against the current `spec.json`.
- Always run the final consistency gate during inspection. Block invalid JSON artifacts, template-heading leakage such as `需求标题` in semantic fields, fixed acceptance text missing from implementation evidence, hidden blocked gates, stale docs/index bindings, and delivery state that claims ready/done while blockers exist.
- Block implementation until spec, technical design, architecture design, test design, delivery plan, delivery plan review, design review, docs quality, delivery docs readiness, git, and edit readiness are complete.
- Delivery docs readiness requires a docs root, doc manifest, and Git repository.
- Git readiness requires evidence that each modify repository fetched the remote and updated the base branch with `pull --ff-only`.
- Require `write_guard_snapshot.json` after the edit permit and before implementation completion can become the next valid stage.
- Report `delivery_plan_review` as the next stage before Git or edit readiness when `delivery_plan_review.json` is missing or blocked.
- Block release until the complete applicable post-implementation chain passes: Runtime post-implementation/pre-push/release checkpoints, implementation completion, post-change report, Harness plan-to-diff/pre-push evidence, write audit, diff impact, post-implementation traceability, change risk, evidence collection, code design quality, code review, frontend acceptance when UI changed, tests, environment promotion, UAT, release change, four required provider attestations, and release binding.
- Treat `can_implement=true` and `can_release=true` as earned terminal readiness states, not merely absence of a single missing file. Required stages, dependencies, profile gates, readiness fields, decisions, digests, and blockers must all agree.
- In `release_readiness` release-only mode, do not demand requirement/design/docs/Git readiness artifacts again; evaluate the applicable release evidence chain directly.

## Output

The output uses schema `codex-delivery-runner-status-v1` and includes the selected profile, detected impacts, stage results, dependency/staleness blockers, final consistency result, next stage/action, and the final `can_implement` and `can_release` decisions.
