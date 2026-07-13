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
- Evaluate the lifecycle registry in `config/workflow-stages.example.yaml` using schema `codex-workflow-stages-v2`, its phase order, explicit dependencies, profile-selected skills, and detected impacts.
- Apply `conditional_skill` stages only when the selected profile requires that skill, and `conditional_impacts` stages only when the artifact set signals a matching impact.
- Block on dependency violations, including an artifact that exists while an applicable prerequisite is missing or not accepted.
- Compare recorded `input_digests` with the current design and specialty artifacts; block when an aggregate design review is stale.
- Validate profile digest bindings such as `open_questions.json.spec_digest` against the current `spec.json`.
- Block implementation until spec, technical design, architecture design, test design, delivery plan, delivery plan review, design review, docs quality, delivery docs readiness, git, and edit readiness are complete.
- Delivery docs readiness requires a docs root, doc manifest, and Git repository.
- Git readiness requires evidence that each modify repository fetched the remote and updated the base branch with `pull --ff-only`.
- Report `delivery_plan_review` as the next stage before Git or edit readiness when `delivery_plan_review.json` is missing or blocked.
- Block release until the complete applicable post-implementation chain passes: implementation completion, post-change report, write audit, diff impact, post-implementation traceability, change risk, evidence collection, code design quality, code review, frontend acceptance when UI changed, tests, environment promotion, UAT, release change, and release binding.
- Treat `can_implement=true` and `can_release=true` as earned terminal readiness states, not merely absence of a single missing file. Required stages, dependencies, profile gates, readiness fields, decisions, digests, and blockers must all agree.
- In `release_readiness` release-only mode, do not demand requirement/design/docs/Git readiness artifacts again; evaluate the applicable release evidence chain directly.

## Output

The output uses schema `codex-delivery-runner-status-v1` and includes the selected profile, detected impacts, stage results, dependency/staleness blockers, next stage/action, and the final `can_implement` and `can_release` decisions.
