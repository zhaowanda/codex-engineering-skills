---
name: artifact-schema-governor
description: Inventory and validate machine-readable artifact schemas emitted by Codex engineering skills. Use when adding or changing gate scripts, release artifacts, synthetic examples, or CI checks to ensure schema names are discoverable, stable, unique, and consistently documented.
---

# Artifact Schema Governor

Use this skill after adding or changing scripts that emit JSON artifacts.

## Command

```bash
python3 skills/core/artifact-schema-governor/scripts/artifact_schema.py --root .
```

## Rules

- Each emitted JSON artifact should include a `schema` value.
- Schema names should be unique enough to identify the artifact contract.
- Scripts that emit schemas should be discoverable from `skills/`.
- Missing schemas are warnings for simple helper scripts and blockers for gate-like scripts.

## Output

The output uses schema `codex-artifact-schema-inventory-v1`.
