---
name: dependency-license-governor
description: Review open-source dependency and license readiness before publishing, accepting dependency changes, or cutting releases. Use to check LICENSE presence, project license metadata, dependency manifest presence, and obvious high-risk license signals in pyproject, requirements, package, or lock files.
category: extractor-analyzer
maturity: deterministic-helper
stage: release
gate: false
---

# Dependency License Governor

Use this skill before publishing or accepting dependency changes.

## Position

```text
dependency or release change
-> dependency-license-governor
-> release-package-governor
-> release approval
```

## Command

```bash
python3 scripts/dependency_license.py --root .
```

## Rules

- Open-source repositories must include a `LICENSE` file.
- Project metadata should declare a license.
- Dependency manifests should be reviewed when present.
- Copyleft or unknown license signals are flagged for maintainer review.
- Do not infer legal approval; route unresolved license risk to maintainers.

## Output

The output uses schema `codex-dependency-license-v1`.

The artifact reports license-file status, project metadata status, dependency manifest review signals, high-risk license warnings, blockers, and follow-up actions.
