---
name: prompt-pack-governor
description: Provide and validate reusable prompt packs for using Codex engineering skills on one-line requests, long PRDs, bugfixes, code review, release readiness, and low-rework implementation. Use when users need standardized prompts that drive the workflow without excessive back-and-forth.
---

# Prompt Pack Governor

Use this skill to list or validate prompt packs for external users.

## Position

```text
prompt authoring or release
-> prompt-pack-governor
-> prompt-effectiveness-governor
-> documentation/release readiness
```

## Commands

```bash
python3 scripts/prompt_pack.py --root . --list
python3 scripts/prompt_pack.py --root . --validate
```

## Rules

- Prompt packs must state the target scenario.
- Prompts must require artifacts, boundaries, evidence, and stop conditions.
- Prompts must avoid private project names and local paths.
- Prompts should guide users to design-first delivery before implementation.
- Release-readiness prompts must require validation and rollback evidence.

## Output

The output uses schema `codex-prompt-pack-v1`.

The artifact reports prompt inventory, scenario coverage, validation blockers, private-data warnings, missing evidence requirements, and stop-condition gaps.
