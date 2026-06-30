# Getting Started

This guide runs the open-core workflow with the synthetic example.

## 0. Normal Path

Preview setup and local checks:

```bash
python3 scripts/codex_eng.py setup
```

Install and check the local skill set:

```bash
python3 scripts/codex_eng.py setup --force
```

List supported scenarios:

```bash
python3 scripts/codex_eng.py scenarios --format markdown
```

For normal requirement handling, run one command:

```bash
python3 scripts/codex_eng.py run docs-governor init \
  --docs-root /tmp/codex-delivery-docs \
  --doc-id REQ-DEMO

python3 scripts/codex_eng.py auto \
  --input examples/synthetic-e2e-case/requirement.md \
  --doc-id REQ-DEMO \
  --docs-root /tmp/codex-delivery-docs \
  --out /tmp/codex-auto-demo \
  --format human
```

With repository understanding:

```bash
python3 scripts/codex_eng.py auto \
  --input examples/synthetic-e2e-case/requirement.md \
  --doc-id REQ-DEMO \
  --repo examples/synthetic-repos/basic-web-service \
  --project basic-web-service \
  --docs-root /tmp/codex-delivery-docs \
  --out /tmp/codex-auto-demo \
  --format human
```

The runner decides which artifacts are missing, verifies the delivery docs repository, skips existing artifacts unless `--force` is provided, and writes `auto_run_summary.json` with workflow profile selection, profile selection reason, next stage, next command, blockers, and implementation/release readiness.

Check the next safe action later:

```bash
python3 scripts/codex_eng.py next --artifact-dir /tmp/codex-auto-demo
```

Preview implementation scope before editing:

```bash
python3 scripts/codex_eng.py implement --artifact-dir /tmp/codex-auto-demo
```

Implementation dry-run blocks until the delivery docs manifest exists and Git evidence proves `fetch` plus `pull --ff-only` on the base branch.

The manual steps below are for debugging individual gates, not the normal path.

## 1. Installation Details

Preview install without writing:

```bash
python3 install.py --dry-run
```

By default, skills are installed to `${CODEX_HOME:-~/.codex}/skills/codex-engineering-skills`.

If you want to install this repository into the local Codex skills directory:

```bash
python3 scripts/codex_eng.py run sync-local-skills --dry-run
python3 scripts/codex_eng.py run sync-local-skills --force
```

Skills are copied into `${CODEX_HOME:-~/.codex}/skills/codex-engineering-skills`.

If you no longer want legacy local skill folders, archive everything except `.system/`, `.backup/`, and `codex-engineering-skills/`:

```bash
python3 scripts/codex_eng.py run sync-local-skills --prune-legacy --dry-run
python3 scripts/codex_eng.py run sync-local-skills --prune-legacy --force
```

## 2. Validate The Repository

```bash
python3 tests/test_privacy_scan.py
python3 scripts/privacy_scan.py --root . --patterns config/private-patterns.example.yaml
```

Fast path:

```bash
python3 scripts/codex_eng.py synthetic-e2e --out-dir /tmp/codex-synthetic
python3 scripts/codex_eng.py inspect --artifact-dir /tmp/codex-synthetic
```

Prompt pack and schema checks:

```bash
python3 scripts/codex_eng.py run prompt-pack --root . --validate
python3 scripts/codex_eng.py run artifact-schema --root .
```

## 3. Understand An Existing Repository

Before designing against a legacy or unfamiliar codebase, generate a project understanding dossier:

```bash
python3 scripts/codex_eng.py project legacy \
  --repo examples/synthetic-repos/basic-web-service \
  --project basic-web-service \
  --type backend \
  --git-url git@example.com:org/basic-web-service.git \
  --overlay-root /tmp/codex-private-overlay \
  --out /tmp/codex-project-understanding
```

Expected outputs:

- `repository_analysis.json`: language, structure, entrypoint, build, test, and CI hints.
- `api_surface.json`: extracted API and route hints.
- `config_surface.json`: configuration file paths and key names only.
- `dependency_surface.json`: dependency ecosystems and build/test hints.
- `git_history.json`: recent commits and hot files when Git history is available.
- `code_index.json`: compact source index for targeted lookup.
- `baseline.json`: machine-readable inferred baseline.
- `baseline_quality.json`: baseline completeness review.
- `human_baseline.md`: readable project summary for maintainers.
- `skills/<project>/SKILL.md`: private project skill.
- `skills/<project>/references/`: expert project references.
- `projects.yaml`: private project registry.
- `indexes/<project>.code_index.json`: canonical private code search index.
- `baseline/<project>.baseline.json`: private legacy baseline.

For real repositories, write outputs to a private overlay or temporary artifact directory. Do not commit generated real project baselines, indexes, endpoint maps, or config surfaces to this open-source repository.

## 4. Ingest Requirement

```bash
python3 skills/core/requirement-document-ingestor/scripts/ingest_requirement.py \
  --input examples/synthetic-e2e-case/requirement.md \
  --doc-id REQ-SYN-001 \
  --out-dir /tmp/codex-synthetic
```

## 5. Normalize Spec

```bash
python3 skills/core/spec-governor/scripts/spec_governor.py normalize \
  --doc-id REQ-SYN-001 \
  --title "Order export" \
  --input /tmp/codex-synthetic/requirement.normalized.txt \
  --out /tmp/codex-synthetic/spec.json
```

If open questions exist, run:

```bash
python3 skills/core/requirement-question-governor/scripts/question_governor.py generate \
  --spec /tmp/codex-synthetic/spec.json \
  --out /tmp/codex-synthetic/open_questions.json
```

## 6. Generate Designs

```bash
python3 skills/core/technical-design-governor/scripts/technical_design.py \
  --spec /tmp/codex-synthetic/spec.json \
  --out /tmp/codex-synthetic/technical_design.json

python3 skills/core/architecture-design-governor/scripts/architecture_design.py \
  --spec /tmp/codex-synthetic/spec.json \
  --technical-design /tmp/codex-synthetic/technical_design.json \
  --out /tmp/codex-synthetic/architecture_design.json
```

## 7. Generate Test And Specialist Reviews

```bash
python3 skills/core/test-design-governor/scripts/test_design.py render \
  --spec /tmp/codex-synthetic/spec.json \
  --technical-design /tmp/codex-synthetic/technical_design.json \
  --architecture-design /tmp/codex-synthetic/architecture_design.json \
  --out /tmp/codex-synthetic/test_design.json

python3 skills/core/performance-governor/scripts/performance.py design \
  --spec /tmp/codex-synthetic/spec.json \
  --technical-design /tmp/codex-synthetic/technical_design.json \
  --architecture-design /tmp/codex-synthetic/architecture_design.json \
  --out /tmp/codex-synthetic/performance_design_review.json || true

python3 skills/core/data-security-governor/scripts/data_security.py design \
  --spec /tmp/codex-synthetic/spec.json \
  --technical-design /tmp/codex-synthetic/technical_design.json \
  --architecture-design /tmp/codex-synthetic/architecture_design.json \
  --out /tmp/codex-synthetic/data_security_review.json || true
```

## 8. Inspect Workflow Status

```bash
python3 skills/core/delivery-runner/scripts/delivery_runner.py inspect \
  --artifact-dir /tmp/codex-synthetic
```

The runner tells you the current stage, missing artifacts, blockers, next command, and whether implementation or release is allowed.

## 9. Connect A Private Overlay

Use `project-runner` and `docs-governor` in a private repository:

```bash
python3 scripts/codex_eng.py project new \
  --project web-app \
  --repo /path/to/web-app \
  --type frontend \
  --git-url git@example.com:org/web-app.git \
  --overlay-root /path/to/private-overlay \
  --default-branch main
```

Do not commit real generated indexes, baseline docs, project paths, or customer artifacts to the open core.
