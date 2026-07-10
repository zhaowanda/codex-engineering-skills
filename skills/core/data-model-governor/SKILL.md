---
name: data-model-governor
description: Generate data model and schema design artifacts for tables, fields, indexes, migrations, history data, consistency, and rollback. Use when requirements mention fields, tables, status, history data, migration, cache data, reports, settlement, payment, or persistence changes.
category: artifact-generator
maturity: expert-gate
stage: design
gate: true
---

# Data Model Governor

Use this skill before implementation when data shape or persistence can change.

## Position

Run after requirement/domain understanding and before database, migration, cache, or test-data planning.

## Rules

- Generate `data_model_design.json`.
- Do not invent table names. If source evidence is insufficient, record blockers or confirmation-required fields.
- Cover ownership, read/write rules, schema changes, indexes, migration/backfill, old data compatibility, rollback, and test data.
- Strongly consistent business data such as money, settlement, payment, permission, and inventory requires explicit consistency and rollback design.

## Command

```bash
python3 scripts/data_model.py \
  --spec artifacts/REQ-001/spec.json \
  --technical-design artifacts/REQ-001/technical_design.json \
  --out artifacts/REQ-001/data_model_design.json
```

## Output

The script writes `codex-data-model-design-v1` with schema decisions, migration strategy, indexes, compatibility, and blockers.
