---
name: skill-installation-governor
description: Install, plan, or validate Codex engineering skills from this open-core repository into a local Codex skills directory. Use when users want one-command installation, dry-run installation planning, overwrite-safe copying, or verification that installed SKILL.md files match the source repository.
---

# Skill Installation Governor

Use this skill to install open-core skills into a local Codex skills directory.

## Commands

```bash
python3 skills/core/skill-installation-governor/scripts/install_skills.py \
  --source . \
  --target ~/.codex/skills/codex-engineering-skills \
  --dry-run
```

```bash
python3 skills/core/skill-installation-governor/scripts/install_skills.py \
  --source . \
  --target ~/.codex/skills/codex-engineering-skills
```

## Rules

- Install only `skills/core` and `skills/templates` by default.
- Refuse to overwrite a non-empty target unless `--force` is provided.
- Validate that copied skill folders contain `SKILL.md`.
- Never install examples, tests, `.git`, private overlays, generated artifacts, or local caches.

## Output

The output uses schema `codex-skill-installation-v1`.
