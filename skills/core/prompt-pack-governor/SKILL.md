---
name: prompt-pack-governor
description: Provide and validate reusable prompt packs for using Codex engineering skills on one-line requests, long PRDs, bugfixes, code review, release readiness, and low-rework implementation. Use when users need standardized prompts that drive the workflow without excessive back-and-forth.
---

# Prompt Pack Governor

Use this skill to list or validate prompt packs for external users.

## Commands

```bash
python3 skills/core/prompt-pack-governor/scripts/prompt_pack.py --root . --list
python3 skills/core/prompt-pack-governor/scripts/prompt_pack.py --root . --validate
```

## Rules

- Prompt packs must state the target scenario.
- Prompts must require artifacts, boundaries, evidence, and stop conditions.
- Prompts must avoid private project names and local paths.

## Output

The output uses schema `codex-prompt-pack-v1`.
