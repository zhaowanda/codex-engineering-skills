---
name: requirement-document-ingestor
description: Ingest and normalize requirement source files before spec-governor. Use when requirements arrive as Markdown, plain text, JSON exports, PDF placeholders, copied online docs, screenshots descriptions, tables, or mixed product notes that need a clean text artifact and source manifest.
---

# Requirement Document Ingestor

Use this skill before `spec-governor`.

## Command

```bash
python3 skills/core/requirement-document-ingestor/scripts/ingest_requirement.py \
  --input requirement.md \
  --doc-id REQ-001 \
  --out-dir artifacts/REQ-001
```

## Rules

- Preserve source references and detected tables/images/process hints.
- Do not claim OCR/PDF extraction succeeded unless text is actually available.
- Write normalized text for `spec-governor`.

## Output

The output uses schema `codex-requirement-ingestion-v1`.
