---
name: docs-governor
description: Initialize and validate a delivery documentation repository structure that separates human-readable documents from machine-readable artifacts. Use when teams need long-lived specs, designs, plans, reviews, releases, baseline docs, and cross-project indexes outside the open core.
category: meta-governor
maturity: deterministic-helper
stage: documentation
gate: false
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
- Before implementation, validate docs root with `--require-git`; a plain local folder is not enough.
- Do not copy secrets, local absolute paths, or private customer data into shareable docs.

## Command

Configure the delivery docs repository once per workspace:

```bash
python3 scripts/docs_governor.py \
  configure \
  --docs-root delivery-docs \
  --git-url git@github.com:your-org/delivery-docs.git
```

Initialize one delivery doc id in the configured docs repository:

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
  --doc-id REQ-001 \
  --require-git
```

## Output

The output uses schema `codex-docs-governor-v1`.

The artifact reports initialized or validated paths, missing structure, blockers, warnings, and next actions.
