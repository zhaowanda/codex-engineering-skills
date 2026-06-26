---
name: dependency-surface-analyzer
description: Analyze dependency and build surface for a source repository. Use when reverse-engineering package managers, dependency files, build command hints, test command hints, and runtime ecosystem before creating private baseline docs.
---

# Dependency Surface Analyzer

Use this skill during project understanding before choosing build, test, dependency, or license-review paths.

## Position

```text
repository-analyzer
-> dependency-surface-analyzer
-> dependency-license-governor / project-baseline-reverser
-> build and test planning
```

## Rules

- Detect dependency manifests, package managers, runtime ecosystems, and likely build/test commands.
- Report hints conservatively when multiple ecosystems appear.
- Do not infer license safety; pass dependency findings to dependency-license-governor for that decision.
- Warn when manifests are absent, ambiguous, generated, or inconsistent.
- Do not install dependencies or mutate lockfiles.
- Treat output as repository surface evidence, not a verified successful build.

## Command

```bash
python3 scripts/dependency_surface.py \
  --repo /path/to/repo \
  --project example \
  --out /tmp/dependency_surface.json
```

## Output

The output uses schema `codex-dependency-surface-v1`.

The artifact reports manifests, ecosystems, dependency manager hints, build/test command hints, warnings, and limitations.
