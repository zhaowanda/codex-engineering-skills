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
- `init` must materialize non-empty requirement-scoped human docs and machine placeholders; empty `human/` or `machine/` directories are not sufficient.
- `sync` must copy generated delivery artifacts into the docs repository by `doc_id` so docs follow the requirement, not just the workspace.
- `sync` must inherit existing expert supplemental artifacts from `machine/raw/<doc_id>` before rendering human docs when the current artifact directory lacks them; source-backed runtime evidence must not be lost during `--force` reruns.
- `sync` must synthesize `runtime_sequence_evidence.json` when it is missing and source-backed evidence exists in `spec.json`, `technical_design.json`, `project_understanding/api_surface.json`, `project_understanding/code_index.json`, and indexed source files. If those inputs are insufficient, report the reason instead of fabricating actor/API/service interactions.
- Runtime entrypoints are not always frontend pages. Runtime evidence must model the trigger source explicitly, including frontend actions, HTTP/API callers, scheduled jobs, MQ consumers, batch jobs, hand-written/custom Task classes, or backend methods, and sequence diagrams must render the confirmed trigger source instead of defaulting to browser/frontend.
- Keep private project docs outside the open-core repository.
- Validate expected folders and manifests before teams rely on the docs repository.
- Human-readable docs default to English. Pass `--doc-language zh` when the requirement or user explicitly asks for Chinese docs.
- Synced human docs should read as formal review documents, not JSON dumps: include background, goals, clarification log, decisions, diagrams, evidence references, test/rollback/release sections, and explicit missing-input explanations.
- Human-readable design docs should expose expert review sections for data model/table schema, multi-system sequence, MQ upstream/downstream trigger mechanism, cache strategy, transaction consistency, and observability when those artifacts exist.
- Prefer language-neutral document models plus i18n rendering for human docs; do not generate English prose first and translate the finished document into Chinese.
- Keep code identifiers, table names, fields, API routes, and user-provided business text unchanged while translating section titles, field labels, statuses, and fixed review phrases.
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
  --doc-id REQ-001 \
  --title "Order export" \
  --doc-language en
```

Sync generated delivery artifacts into the docs repository:

```bash
python3 scripts/docs_governor.py \
  sync \
  --docs-root delivery-docs \
  --doc-id REQ-001 \
  --title "Order export" \
  --doc-language en \
  --artifact-dir artifacts/REQ-001
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

The artifact reports initialized, synced, or validated paths, missing structure, blockers, warnings, and next actions. A valid initialized doc id includes non-empty `human/specs`, `human/designs`, `human/releases`, `machine/specs`, `machine/designs`, `machine/reviews`, and `machine/releases` files.
