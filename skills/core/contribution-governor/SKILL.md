---
name: contribution-governor
description: Govern open-source contribution readiness for Codex engineering skills. Use when adding or reviewing CONTRIBUTING.md, contribution workflow docs, local development commands, PR review requirements, issue templates, CI requirements, or maintainer contribution rules.
---

# Contribution Governor

Use this skill before accepting external contributions or publishing contribution guidance.

## Command

```bash
python3 scripts/contribution.py --root .
```

## Rules

- `CONTRIBUTING.md` must exist.
- Contribution docs must mention local tests, privacy scan, skill health, PR review, issue linkage, and no private data.
- GitHub issue and PR templates must exist.
- CI validation workflow must exist.

## Output

The output uses schema `codex-contribution-governance-v1`.
