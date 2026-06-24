---
name: docs-governor
description: Initialize and validate a delivery documentation repository structure that separates human-readable documents from machine-readable artifacts. Use when teams need long-lived specs, designs, plans, reviews, releases, baseline docs, and cross-project indexes outside the open core.
---

# Docs Governor

Use this skill for a private delivery docs repository.

## Command

```bash
python3 skills/core/docs-governor/scripts/docs_governor.py \
  init \
  --docs-root delivery-docs \
  --doc-id REQ-001
```

Validate:

```bash
python3 skills/core/docs-governor/scripts/docs_governor.py \
  validate \
  --docs-root delivery-docs \
  --doc-id REQ-001
```

## Output

The output uses schema `codex-docs-governor-v1`.
