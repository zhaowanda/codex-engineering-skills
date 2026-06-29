---
name: docs-readability-governor
description: Review open-source documentation readability and onboarding clarity. Use when publishing README or docs changes to check start path, installation and validation commands, boundary explanation, scenario coverage, FAQ presence, local-path safety, link health, and overly thin docs.
category: meta-governor
maturity: deterministic-helper
stage: documentation
gate: false
---

# Docs Readability Governor

Use this skill before publishing docs.

## Command

```bash
python3 scripts/docs_readability.py --root .
```

## Rules

- README must include start path, boundary, validation, and maintenance checks.
- Required docs must exist.
- Docs must not contain local absolute paths or private markers.
- Very thin public docs produce warnings.

## Output

The output uses schema `codex-docs-readability-v1`.
