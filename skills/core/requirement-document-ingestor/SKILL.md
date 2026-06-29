---
name: requirement-document-ingestor
description: Ingest and normalize requirement source files before spec-governor. Use when requirements arrive as Markdown, plain text, JSON exports, PDF placeholders, copied online docs, screenshots descriptions, tables, or mixed product notes that need a clean text artifact and source manifest.
category: extractor-analyzer
maturity: deterministic-helper
stage: requirements
gate: false
---

# Requirement Document Ingestor

Use this skill before `spec-governor`.

## Position

```text
raw requirement source
-> requirement-document-ingestor
-> spec-governor
-> requirement-question-governor
```

## Command

```bash
python3 scripts/ingest_requirement.py \
  --input requirement.md \
  --doc-id REQ-001 \
  --out-dir artifacts/REQ-001
```

## Rules

- Preserve source references and detected tables/images/process hints.
- Do not claim OCR/PDF extraction succeeded unless text is actually available.
- Write normalized text for `spec-governor`.
- Keep original requirement facts separate from inferred summaries.
- Flag unsupported file types or empty inputs as warnings or blockers.

## Output

The output uses schema `codex-requirement-ingestion-v1`.

The artifact reports normalized requirement text, source manifest, detected structures, unsupported inputs, blockers, warnings, and next command hints.
