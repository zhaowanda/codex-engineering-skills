---
name: release-package-governor
description: Validate open-source release package readiness for Codex engineering skills. Use before tagging or publishing releases to check required repository files, version consistency, changelog entries, package manifest contents, installability signals, and release dry-run evidence without creating a real release.
---

# Release Package Governor

Use this skill before creating a tag or GitHub release.

## Position

```text
version-release-governor
-> release-package-governor
-> release evidence / tag preparation
```

## Command

```bash
python3 scripts/release_package.py --root .
```

## Rules

- Required files and directories must exist.
- `pyproject.toml` version must have a matching `CHANGELOG.md` entry.
- Release manifest is dry-run only and must not create archives or tags.

## Output

The output uses schema `codex-release-package-v1`.

The artifact reports package manifest, required path checks, version/tag expectation, dry-run status, blockers, and warnings.
