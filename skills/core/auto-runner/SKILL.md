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
-> Requirement IR / Evidence Bundle / applicability decision
-> requirement/spec/design/test/plan/review artifacts
-> delivery-runner inspect
```

## Rules

- Default behavior is read-only analysis and artifact generation.
- Do not create Git branches, edit business source files, commit, deploy, or release.
- After receiving a requirement, run this read-only workflow before any source/config/test write.
- Implementation may start only when delivery inspection reports `can_implement=true`.
- `can_implement=true` requires technical design, architecture design, design review, delivery plan review, Git worktree evidence with fetch plus `pull --ff-only`, and edit permit readiness.
- If a user asks to implement immediately from a requirement, stop and run this workflow first; do not edit code from requirement intake alone.
- Skip existing artifacts unless `--force` is provided.
- `--force` must not downgrade previously captured expert evidence; docs sync is expected to preserve source-backed supplemental artifacts such as runtime sequence evidence from the delivery docs repository.
- Run project understanding only when both `--repo` and `--project` are provided.
- For repository-backed runs, generate requirement-specific source-location evidence after project understanding and before spec/design.
- Stop after spec and requirement questions when requirement understanding or source-location confirmation blocks design. Do not emit pass-looking design, test, or plan artifacts.
- Treat impact applicability as `required`, `conditional`, or `excluded`; do not promote generic runtime data, API references, or read-only repositories into specialist profiles without change evidence.
- Prefer `evidence_bundle.json` over full project indexes in downstream design and planning.
- Return non-zero when the top-level decision is blocked (`2`) or the runner fails (`3`).
- Run Harness validation after full artifact generation to enforce artifact-size budgets and prevent reference-only anchors from becoming edit targets.
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

## Output

The output uses schema `codex-auto-runner-summary-v1`.

The artifact reports doc id, output directory, executed steps, generated artifacts, skipped artifacts, workflow profile, applicability decisions, unified stage result, blockers, inspect status, next stage, next command, and implementation/release readiness.
