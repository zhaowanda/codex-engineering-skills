---
name: auto-runner
description: One-command workflow entrypoint for Codex engineering skills. Use when users want Codex to ingest a requirement, optionally understand a repository, generate design/test/plan artifacts, inspect workflow status, and decide the next safe action without manually invoking each skill.
category: template-runner
maturity: orchestrator
stage: workflow-orchestration
gate: false
---

# Auto Runner

Use this skill as the default one-command entrypoint for requirement handling.

## Position

```text
user requirement
-> auto-runner
-> Agent Runtime session / intake checkpoint
-> Requirement IR / Evidence Bundle / applicability decision
-> requirement/spec/design/test/plan/review artifacts
-> Agent Runtime design checkpoint / Harness validation
-> delivery-runner inspect
```

## Rules

- Default behavior is read-only analysis and artifact generation.
- Start or resume one `codex-agent-runtime-session-v1` session per doc id. Record repository commands and imported editor/MCP/browser events in the append-only SHA-256 event chain without secrets or raw credentials.
- Require Runtime checkpoints at intake, design, pre-edit, post-implementation, pre-push, release, and close. A checkpoint is valid only when the session chain verifies and its required actions and evidence exist.
- Do not create Git branches, edit business source files, commit, deploy, or release.
- After receiving a requirement, run this read-only workflow before any source/config/test write.
- Implementation may start only when delivery inspection reports `can_implement=true`.
- `can_implement=true` requires technical design, architecture design, design review, delivery plan review, Git worktree evidence with fetch plus `pull --ff-only`, and edit permit readiness.
- If a user asks to implement immediately from a requirement, stop and run this workflow first; do not edit code from requirement intake alone.
- Skip existing artifacts unless `--force` is provided.
- `--force` must not downgrade previously captured expert evidence; docs sync is expected to preserve source-backed supplemental artifacts such as runtime sequence evidence from the delivery docs repository.
- Run project understanding only when both `--repo` and `--project` are provided.
- For repository-backed runs, generate requirement-specific source-location evidence after project understanding and before spec/design.
- When `--project` resolves an installed company project skill, consume relevant reference excerpts into Evidence Bundle with file digests and provenance; do not copy full private references.
- Propagate the canonical scope model through design, planning, edit readiness, post-change checks, and acceptance evidence.
- Stop after spec and requirement questions when requirement understanding or source-location confirmation blocks design. Do not emit pass-looking design, test, or plan artifacts.
- Do not stop for optional clarification/advisory questions when `spec.design_allowed=true` and `open_questions.json.decision=pass`; carry those advisories into design context instead of forcing another Spec round.
- When requirement clarification blocks progress, return `python3 scripts/codex_eng.py clarify --artifact-dir <out>` as the next command. Do not prompt inside captured `auto --format human` execution.
- On a same-directory rerun, merge non-empty `clarification_answers.md` with `requirement.normalized.txt` into `requirement.clarified.txt`; use that file for source-location evidence and Spec so answers change downstream evidence instead of merely closing questions.
- Treat impact applicability as `required`, `conditional`, or `excluded`; do not promote generic runtime data, API references, or read-only repositories into specialist profiles without change evidence.
- Prefer `evidence_bundle.json` over full project indexes in downstream design and planning.
- Return non-zero when the top-level decision is blocked (`2`) or the runner fails (`3`).
- Run the source-location Harness after repository evidence and before Spec so stale indexes, missing files, weak anchors, and source-digest drift stop guessed code locations.
- Run the design Harness after plan review and before docs/Git readiness. Enforce artifact budgets, confirmed modify targets, business process flow, applicable system sequence, architecture integration sequence, and state-machine coverage.
- Use the post-implementation Harness to bind actual changed files to delivery-plan scope.
- Use the pre-push Harness to require accepted post-change, traceability, test, review, project-skill-index, and current-commit evidence.
- Load defaults from `config/harness-policy.example.yaml`; keep organization/provider policy in a private overlay.
- Load generic Runtime controls from `config/agent-runtime-policy.example.yaml`. Open core validates provider attestations; provider adapters, verification keys, credentials, and organization endpoints remain private.
- Validate provider attestations against subject, supported provider type, issued/verified timestamps, verifier identity, immutable URI, and SHA-256 evidence digest.
- Validate exceptions as `codex-governance-waiver-v1`; reject missing owner/approver identity, self-approval, uncovered gates, expiry, absent compensating controls, or missing immutable audit retention.
- Human-readable delivery docs default to automatic language detection: if the requirement asks for Chinese docs, generate Chinese; otherwise generate English.
- Use `--doc-language en|zh|auto` to force or auto-detect the human doc language.
- After docs sync, run human documentation review and write `docs_quality.json`.
- Always finish by running delivery inspection and writing `auto_run_summary.json`.
- Surface blockers and next action instead of hiding failed gates.

## Command

```bash
python3 scripts/auto_runner.py \
  --input requirement.md \
  --doc-id REQ-001 \
  --title "Order export" \
  --repo /path/to/project \
  --project my-project \
  --doc-language auto \
  --out artifacts/REQ-001
```

Minimal usage:

```bash
python3 scripts/auto_runner.py --input requirement.md
```

Repository-level shortcut:

```bash
python3 scripts/codex_eng.py auto --input requirement.md
```

Runtime inspection and controlled advancement:

```bash
python3 scripts/codex_eng.py runtime verify --artifact-dir artifacts/REQ-001
python3 scripts/codex_eng.py runtime advance --artifact-dir artifacts/REQ-001 --name post_implementation
python3 scripts/codex_eng.py runtime advance --artifact-dir artifacts/REQ-001 --name pre_push
python3 scripts/codex_eng.py runtime advance --artifact-dir artifacts/REQ-001 --name release \
  --provider artifacts/REQ-001/runtime/providers/ci.json \
  --provider artifacts/REQ-001/runtime/providers/change_management.json \
  --provider artifacts/REQ-001/runtime/providers/deployment.json \
  --provider artifacts/REQ-001/runtime/providers/observability.json
python3 scripts/codex_eng.py runtime advance --artifact-dir artifacts/REQ-001 --name close
```

Post-implementation and pre-push checkpoints:

```bash
python3 scripts/harness_validation.py \
  --artifact-dir artifacts/REQ-001 \
  --checkpoint post_implementation \
  --policy config/harness-policy.example.yaml \
  --out artifacts/REQ-001/harness/post_implementation.json

python3 scripts/harness_validation.py \
  --artifact-dir artifacts/REQ-001 \
  --checkpoint pre_push \
  --policy config/harness-policy.example.yaml \
  --repo /path/to/repo \
  --out artifacts/REQ-001/harness/pre_push.json
```

## Output

The auto-run output uses schema `codex-auto-runner-summary-v1`. Harness checkpoints use `codex-harness-checkpoint-v2`; Runtime sessions, events, checkpoints, provider attestations, and governance waivers use `codex-agent-runtime-session-v1`, `codex-agent-runtime-event-v1`, `codex-runtime-checkpoint-v1`, `codex-provider-attestation-v1`, and `codex-governance-waiver-v1`.

The artifact reports doc id, output directory, executed steps, generated artifacts, skipped artifacts, workflow profile, applicability decisions, unified stage result, blockers, inspect status, next stage, next command, and implementation/release readiness.
