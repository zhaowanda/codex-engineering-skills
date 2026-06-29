---
name: version-release-governor
description: Govern open-source version and release readiness. Use before tagging, publishing a GitHub release, changing pyproject version, or preparing changelog and release notes to enforce SemVer, changelog entries, compatibility notes, migration notes, and release evidence.
category: meta-governor
maturity: deterministic-helper
stage: release
gate: false
---

# Version Release Governor

Use this skill before creating a release tag.

## Position

```text
change preparation
-> version-release-governor
-> release-package-governor
-> tag/release publishing
```

## Command

```bash
python3 scripts/version_release.py \
  --root . \
  --version 0.2.0
```

## Rules

- Versions must follow SemVer.
- `pyproject.toml` version and requested release version must match when both exist.
- `CHANGELOG.md` must contain the release version.
- Breaking changes need migration notes.

## Output

The output uses schema `codex-version-release-v1`.

The artifact reports requested version, project version, changelog status, SemVer validation, migration-note expectations, blockers, and warnings.
