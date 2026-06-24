---
name: ci-templates
description: Generate CI templates for Codex engineering skills repositories. Use when setting up GitHub Actions or GitLab CI to run Python compilation, framework tests, and privacy scanning for the open-core or a private overlay repository.
---

# CI Templates

Use this skill to create CI files for repository validation.

## Supported Providers

- `github`: writes `.github/workflows/validate.yml`
- `gitlab`: writes `.gitlab-ci.yml`

## Command

Generate GitHub Actions:

```bash
python3 skills/templates/ci-templates/scripts/render_ci.py \
  --provider github \
  --out .github/workflows/validate.yml
```

Generate GitLab CI:

```bash
python3 skills/templates/ci-templates/scripts/render_ci.py \
  --provider gitlab \
  --out .gitlab-ci.yml
```

## Validation Scope

The generated CI runs:

- Python syntax compilation for scripts and tests.
- All `tests/test_*.py` files.
- Privacy scan using `config/private-patterns.example.yaml`.

Private overlays should add their own registry, project-skill, and generated-index checks without committing private artifacts to the open core.
