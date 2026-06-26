---
name: artifact-schema-governor
description: Inventory and validate machine-readable artifact schemas emitted by Codex engineering skills. Use when adding or changing gate scripts, release artifacts, synthetic examples, or CI checks to ensure schema names are discoverable, stable, unique, and consistently documented.
---

# Artifact Schema Governor

Use this skill after adding or changing scripts that emit JSON artifacts.

## Position

```text
script/schema changes
-> artifact-schema-governor
-> compatibility-governor
-> release-package-governor
```

## Command

```bash
python3 scripts/artifact_schema.py --root .
```

## Rules

- Each emitted JSON artifact should include a `schema` value.
- Schema names should be unique enough to identify the artifact contract.
- Scripts that emit schemas should be discoverable from `skills/`.
- Missing schemas are warnings for simple helper scripts and blockers for gate-like scripts.
- Schema renames require compatibility review and migration notes.

## Output

The output uses schema `codex-artifact-schema-inventory-v1`.

The artifact reports discovered schema names, source scripts, missing schema emitters, duplicate or unstable contracts, blockers, and warnings.
