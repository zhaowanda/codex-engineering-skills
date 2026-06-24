---
name: artifact-splitter
description: Split machine-readable delivery artifacts from human-readable review documents. Use when technical designs, architecture designs, delivery plans, review results, permits, or test evidence need readable summaries without leaking local paths or replacing gate JSON.
---

# Artifact Splitter

Use this skill after generating machine-readable JSON artifacts.

## Purpose

Machine artifacts and human documents serve different readers:

- Machine JSON is strict input for gates and scripts.
- Human Markdown explains intent, decisions, risks, status, and next actions.

Do not mix them into one file.

## Rules

- Keep original JSON artifacts unchanged.
- Generate human-readable Markdown next to or outside machine artifacts.
- Do not expose absolute local paths in human docs by default.
- Preserve artifact references through logical labels and sanitized relative names.
- Human docs must summarize decisions, option tradeoffs, risks, blockers, evidence, and next actions.
- Machine JSON remains the source of truth for automated gates.

## Commands

Generate human docs from artifacts:

```bash
python3 skills/templates/artifact-splitter/scripts/split_artifacts.py \
  --doc-id REQ-001-checkout \
  --title "Checkout discount display" \
  --technical-design artifacts/design/technical_design.json \
  --architecture-design artifacts/design/architecture_design.json \
  --design-review artifacts/design/design_architecture_review.json \
  --delivery-plan artifacts/delivery_plan.json \
  --out-dir artifacts/human
```

Include absolute paths only for private internal use:

```bash
python3 skills/templates/artifact-splitter/scripts/split_artifacts.py \
  --doc-id REQ-001-checkout \
  --title "Checkout discount display" \
  --delivery-plan artifacts/delivery_plan.json \
  --out-dir artifacts/human \
  --include-local-paths
```

## Output

The splitter writes:

- `human_summary.md`: readable requirement delivery summary.
- `artifact_manifest.json`: logical artifact references and sanitization status.

Human docs are review aids. They do not replace JSON gates.
