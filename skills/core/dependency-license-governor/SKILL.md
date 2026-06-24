---
name: dependency-license-governor
description: Review open-source dependency and license readiness before publishing, accepting dependency changes, or cutting releases. Use to check LICENSE presence, project license metadata, dependency manifest presence, and obvious high-risk license signals in pyproject, requirements, package, or lock files.
---

# Dependency License Governor

Use this skill before publishing or accepting dependency changes.

## Command

```bash
python3 skills/core/dependency-license-governor/scripts/dependency_license.py --root .
```

## Rules

- Open-source repositories must include a `LICENSE` file.
- Project metadata should declare a license.
- Dependency manifests should be reviewed when present.
- Copyleft or unknown license signals are flagged for maintainer review.

## Output

The output uses schema `codex-dependency-license-v1`.
