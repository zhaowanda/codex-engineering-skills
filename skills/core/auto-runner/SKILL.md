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
-> requirement/spec/design/test/plan/review artifacts
-> delivery-runner inspect
```

## Rules

- Default behavior is read-only analysis and artifact generation.
- Do not create Git branches, edit business source files, commit, deploy, or release.
- Skip existing artifacts unless `--force` is provided.
- Run project understanding only when both `--repo` and `--project` are provided.
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

The artifact reports doc id, output directory, executed steps, generated artifacts, skipped artifacts, workflow profile, profile selection reason, blockers, inspect status, next stage, next command, and implementation/release readiness.
