---
name: repository-analyzer
description: Analyze a source repository structure for generic project understanding. Use when reverse-engineering an unfamiliar codebase to identify languages, frameworks, top-level modules, entrypoint hints, test hints, CI files, configuration files, and build files before generating private baseline docs.
category: extractor-analyzer
maturity: deterministic-helper
stage: project-understanding
gate: false
---

# Repository Analyzer

Use this skill to create a neutral repository analysis artifact.

## Position

```text
new or unfamiliar repository
-> repository-analyzer
-> api/config/dependency/git surface extractors
-> project-baseline-reverser
```

## Rules

- Summarize repository structure, languages, frameworks, entrypoints, tests, CI, config, and build files.
- Do not read secrets or include private values from configuration files.
- Treat findings as hints requiring direct source verification before implementation.
- Warn on empty, generated-only, or unusually large repositories.
- Store real-project analysis in private overlays or temporary artifacts.

## Command

```bash
python3 scripts/repository_analyzer.py \
  --repo /path/to/repo \
  --project example \
  --out /tmp/repository_analysis.json
```

## Output

The output uses schema `codex-repository-analysis-v1`.

The artifact reports project metadata, detected languages, framework hints, entrypoints, test hints, CI/config/build files, warnings, and limitations.
