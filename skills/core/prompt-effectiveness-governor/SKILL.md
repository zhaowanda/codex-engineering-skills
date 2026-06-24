---
name: prompt-effectiveness-governor
description: Review reusable prompt effectiveness for reducing Codex rework. Use when adding or changing prompts to ensure they enforce design-first delivery, scope boundaries, Git readiness, test evidence, stop conditions, artifact outputs, and token-saving behavior appropriate to each prompt scenario.
---

# Prompt Effectiveness Governor

Use this skill after editing prompt packs.

## Command

```bash
python3 skills/core/prompt-effectiveness-governor/scripts/prompt_effectiveness.py --root .
```

## Rules

- Every prompt needs stop conditions and evidence.
- Implementation prompts must mention design, boundary, Git, tests, artifacts, and token/source-reading strategy.
- Review and release prompts must block approval/release when evidence is missing.

## Output

The output uses schema `codex-prompt-effectiveness-v1`.
