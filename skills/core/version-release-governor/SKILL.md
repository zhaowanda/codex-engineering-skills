---
name: version-release-governor
description: Govern open-source version and release readiness. Use before tagging, publishing a GitHub release, changing pyproject version, or preparing changelog and release notes to enforce SemVer, changelog entries, compatibility notes, migration notes, and release evidence.
---

# Version Release Governor

Use this skill before creating a release tag.

## Command

```bash
python3 skills/core/version-release-governor/scripts/version_release.py \
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
