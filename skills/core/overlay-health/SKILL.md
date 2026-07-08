---
name: overlay-health
description: Check private overlay consistency for project registry, project skills, indexes, baseline docs, and delivery docs manifests. Use in private repositories before team rollout or after project onboarding.
category: meta-governor
maturity: deterministic-helper
stage: meta
gate: false
---

# Overlay Health

Use this skill before rolling out a private overlay or after onboarding/changing project skills.

## Position

```text
project-onboard / private overlay edits
-> overlay-health
-> framework-config-governor / team rollout
```

## Rules

- Require a project registry for private overlay use.
- Check that referenced project skills, generated indexes, baseline docs, and delivery docs manifests exist when configured.
- Accept either `projects.yaml` or `registry/projects.json`; when both exist, merge JSON analysis metadata with YAML project assets.
- Resolve project skills in both repository layout (`skills/<project>/SKILL.md`) and installed company layout (`<project>/SKILL.md`).
- Treat skills marked `skill_type: tool`, `kind: tool`, `governor`, or `helper` as non-project skills and skip project index/baseline checks for them.
- Block missing required overlay structure; warn on optional but incomplete generated artifacts.
- Do not publish private overlay outputs to the open-core repository.
- Treat overlay health as environment readiness, not application correctness.

## Command

```bash
python3 scripts/overlay_health.py \
  --overlay-root overlay
```

## Output

The output uses schema `codex-overlay-health-v1`.

The artifact reports registry status, project skill status, index/baseline/docs manifest checks, blockers, and warnings.
