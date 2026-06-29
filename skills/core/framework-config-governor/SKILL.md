---
name: framework-config-governor
description: Validate Codex engineering skills framework configuration and private overlay wiring. Use when setting up the open-core repository, connecting a private project registry, checking required delivery gates, or preparing the framework for team use.
category: meta-governor
maturity: deterministic-helper
stage: meta
gate: false
---

# Framework Config Governor

Use this skill before teams run the workflow on real repositories.

## Scope

- Validate the open-core framework config.
- Validate an optional private project registry.
- Detect missing delivery lanes, gate lists, branch settings, quality thresholds, and artifact paths.
- Detect private overlay material accidentally placed in open-core paths.

## Command

```bash
python3 scripts/framework_config.py \
  validate \
  --framework config/framework.example.yaml \
  --project-registry examples/project-registry/projects.example.yaml
```

With explicit open-core root:

```bash
python3 scripts/framework_config.py \
  validate \
  --framework config/framework.example.yaml \
  --project-registry examples/project-registry/projects.example.yaml \
  --open-core-root .
```

## Rules

- `block` if framework schema or required sections are missing.
- `block` if required delivery lanes or gates are missing.
- `block` if project registry schema is invalid or project entries lack name/root/type/default branch/skill.
- `block` if a project root points inside the open-core repository.
- `warn` if paths use unresolved environment placeholders.
- `warn` if project registry uses placeholder roots or missing test strategy.
- `pass` only when blocking config defects are absent.

## Output

The output uses schema `codex-framework-config-validation-v1`.

Decision values:

- `pass`
- `warn`
- `block`
