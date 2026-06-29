---
name: config-surface-extractor
description: Extract configuration surface hints from a source repository without exposing secret values. Use when reverse-engineering config files, environment keys, Docker/CI config, feature flag hints, or private overlay baseline docs.
category: extractor-analyzer
maturity: deterministic-helper
stage: project-understanding
gate: false
---

# Config Surface Extractor

Use this skill during project understanding to identify runtime configuration shape without collecting values.

## Position

```text
repository-analyzer
-> config-surface-extractor
-> configuration-governor / project-baseline-reverser
-> environment readiness
```

## Rules

- Extract configuration file paths, key names, environment variable names, and feature-flag hints only.
- Never copy secret values, tokens, passwords, certificates, connection strings, or customer-specific values.
- Prefer redacted key-level evidence over raw config excerpts.
- Warn when config files are present but no keys can be safely inferred.
- Store real-project outputs in private overlays or temporary artifacts, not open-core docs.
- Treat CI, Docker, environment, and application config files as part of the configuration surface.

## Command

```bash
python3 scripts/config_surface.py \
  --repo /path/to/repo \
  --project example \
  --out /tmp/config_surface.json
```

## Output

The output uses schema `codex-config-surface-v1`.

The artifact includes discovered config files, key names, environment hints, warnings, and redaction limitations.
