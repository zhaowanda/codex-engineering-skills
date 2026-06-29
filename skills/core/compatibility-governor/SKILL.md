---
name: compatibility-governor
description: Review compatibility risks for open-core skill changes. Use when changing skill names, deleting skills, changing JSON schema names, changing CLI command names, or preparing a release that may break existing users.
category: meta-governor
maturity: deterministic-helper
stage: meta
gate: false
---

# Compatibility Governor

Use this skill before merging breaking changes or publishing a release.

## Command

```bash
python3 scripts/compatibility.py --root .
```

## Rules

- Skill deletions or renames require migration notes.
- Schema deletions or renames require migration notes.
- CLI command deletions require migration notes.
- `CHANGELOG.md` should contain migration notes when compatibility warnings exist.

## Output

The output uses schema `codex-compatibility-review-v1`.
