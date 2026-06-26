---
name: docs-governor
description: Initialize and validate a delivery documentation repository structure that separates human-readable documents from machine-readable artifacts. Use when teams need long-lived specs, designs, plans, reviews, releases, baseline docs, and cross-project indexes outside the open core.
---

# Docs Governor

Use this skill for a private delivery docs repository.

## Position

```text
delivery docs repository setup
-> docs-governor
-> artifact-splitter / human-doc-reviewer
-> long-lived delivery records
```

## Rules

- Separate human-readable documents from machine-readable gate artifacts.
- Require stable doc ids for requirement-specific folders.
- Keep private project docs outside the open-core repository.
- Validate expected folders and manifests before teams rely on the docs repository.
- Do not copy secrets, local absolute paths, or private customer data into shareable docs.

## Command

```bash
python3 scripts/docs_governor.py \
  init \
  --docs-root delivery-docs \
  --doc-id REQ-001
```

Validate:

```bash
python3 scripts/docs_governor.py \
  validate \
  --docs-root delivery-docs \
  --doc-id REQ-001
```

## Output

The output uses schema `codex-docs-governor-v1`.

The artifact reports initialized or validated paths, missing structure, blockers, warnings, and next actions.
