---
name: repository-analyzer
description: Analyze a source repository structure for generic project understanding. Use when reverse-engineering an unfamiliar codebase to identify languages, frameworks, top-level modules, entrypoint hints, test hints, CI files, configuration files, and build files before generating private baseline docs.
---

# Repository Analyzer

Use this skill to create a neutral repository analysis artifact.

## Command

```bash
python3 skills/core/repository-analyzer/scripts/repository_analyzer.py \
  --repo /path/to/repo \
  --project example \
  --out /tmp/repository_analysis.json
```

## Output

The output uses schema `codex-repository-analysis-v1`.
