---
name: skill-health
description: Check open-core skill repository health. Use before release or contribution review to validate SKILL.md frontmatter, script presence, Python compilation, README skill listing, roadmap status, tests, and privacy scan readiness.
---

# Skill Health

Use this skill before contribution review, release packaging, or large skill refactors.

## Position

```text
skill/documentation changes
-> skill-health
-> benchmark-governor
-> release-package-governor
```

## Rules

- Every skill must have valid frontmatter with `name` and `description`.
- Skill names should align with folder paths.
- Skills should be listed in README by path, folder, or name.
- Python scripts under skill folders must compile.
- Tests must exist for the repository.
- Roadmap should contain completion markers for release tracking.

## Command

```bash
python3 scripts/skill_health.py \
  --root .
```

## Output

The output uses schema `codex-skill-health-v1`.

The artifact reports skill count, blockers, warnings, and a pass/warn/block decision.
