---
name: ci-templates
description: Generate CI templates for Codex engineering skills repositories. Use when setting up GitHub Actions or GitLab CI to run Python compilation, framework tests, and privacy scanning for the open-core or a private overlay repository.
category: template-runner
maturity: template
stage: meta
gate: false
---

# CI Templates

Use this skill to create CI files for repository validation.

## Position

```text
repository setup / release package preparation
-> ci-templates
-> contribution-governor / release-package-governor
-> pull request validation
```

## Supported Providers

- `github`: writes `.github/workflows/validate.yml`
- `gitlab`: writes `.gitlab-ci.yml`

## Rules

- Generate validation templates only; do not run CI or commit generated files automatically.
- Include Python compilation, framework tests, privacy scan, and open-source maintenance checks where supported.
- Private overlays should extend generated CI with registry and private-artifact checks without publishing private data.
- Prefer `python3 -m pytest -q` for local developer guidance; generated CI may use direct test-file execution if provider templates require no extra dependencies.
- Treat generated files as starting templates that project maintainers can review before adoption.
- Block generation when the requested provider is unsupported or the output path does not match the provider convention.
- Warn when a repository lacks expected test, privacy-scan, or maintenance-check inputs; generated CI should not imply nonexistent coverage.

## Command

Generate GitHub Actions:

```bash
python3 scripts/render_ci.py \
  --provider github \
  --out .github/workflows/validate.yml
```

Generate GitLab CI:

```bash
python3 scripts/render_ci.py \
  --provider gitlab \
  --out .gitlab-ci.yml
```

## Validation Scope

The generated CI runs:

- Python syntax compilation for scripts and tests.
- All `tests/test_*.py` files.
- Privacy scan using `config/private-patterns.example.yaml`.

Private overlays should add their own registry, project-skill, and generated-index checks without committing private artifacts to the open core.

## Output

The renderer writes either `.github/workflows/validate.yml` or `.gitlab-ci.yml`.

Decision values:

- `pass`: the requested provider is supported and the template contains the expected validation jobs.
- `warn`: the template is generated but repository inputs are incomplete and maintainers must review the missing coverage.
- `block`: the provider, output path, or repository state prevents generating a trustworthy template.

Generated CI should compile Python files, run framework tests, run the privacy scan, and execute open-source maintenance checks appropriate for the selected provider. Any warnings or blockers must be reported with the final decision.
