---
name: skill-health
description: Check open-core skill repository health. Use before release or contribution review to validate SKILL.md frontmatter, script presence, Python compilation, README skill listing, roadmap status, tests, and privacy scan readiness.
---

# Skill Health

## Command

```bash
python3 skills/core/skill-health/scripts/skill_health.py \
  --root .
```

## Output

The output uses schema `codex-skill-health-v1`.
