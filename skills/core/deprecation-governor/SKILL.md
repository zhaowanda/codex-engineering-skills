---
name: deprecation-governor
description: Review deprecation and migration readiness for Codex engineering skills. Use when skill names, schemas, CLI commands, prompts, or public workflows may be renamed, removed, or replaced and need notices, migration paths, compatibility windows, and removal policy.
---

# Deprecation Governor

Use this skill before removing or renaming public contracts.

## Position

```text
public contract change
-> deprecation-governor
-> compatibility-governor
-> release notes / migration guidance
```

## Command

```bash
python3 scripts/deprecation.py --root .
```

## Rules

- `docs/deprecation-policy.md` must exist.
- Policy must mention notice, migration, compatibility window, and removal.
- Compatibility warnings require migration or deprecation notes.
- Removed or renamed public commands require user-facing migration guidance.
- Schema or skill name changes require a compatibility window unless explicitly documented as breaking.

## Output

The output uses schema `codex-deprecation-review-v1`.

The artifact reports policy coverage, notice and migration readiness, compatibility-window expectations, removal-rule blockers, and warnings.
