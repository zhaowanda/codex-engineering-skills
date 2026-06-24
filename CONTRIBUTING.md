# Contributing

Thanks for improving Codex Engineering Skills. This repository is open core: keep private overlays, private data, customer artifacts, generated indexes, and organization-specific project names out of contributions.

## Local Development

Run the full local validation before opening a pull request. The required checks include Python compilation, all tests, privacy scan, and skill health:

```bash
python3 -m py_compile $(find skills tests scripts -name '*.py' | tr '\n' ' ')
for t in tests/test_*.py; do python3 "$t"; done
python3 scripts/privacy_scan.py --root . --patterns config/private-patterns.example.yaml
python3 skills/core/skill-health/scripts/skill_health.py --root .
```

## Pull Request Expectations

- Link an issue or explain why no issue exists.
- Describe scope and out-of-scope items.
- Include tests and evidence.
- Explain risk, rollback, and release notes.
- Do not include private data, customer data, local absolute paths, secrets, private registries, or generated private overlays.

## Review Rules

Maintainers review for workflow correctness, privacy safety, skill structure, tests, docs, and compatibility. Changes to schemas, CLI commands, or skill names require migration notes in `CHANGELOG.md`.

## Issue Rules

Use bug reports for reproducible failures and feature requests for new generic open-core capabilities. Security-sensitive issues should follow `SECURITY.md`, not public issue comments.
