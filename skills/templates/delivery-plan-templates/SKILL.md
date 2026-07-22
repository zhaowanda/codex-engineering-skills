---
name: delivery-plan-templates
description: Generate delivery plan JSON artifacts from reviewed technical and architecture designs. Use after design-architecture-reviewer passes and before Git preparation, edit readiness, implementation, testing, or release planning.
category: template-runner
maturity: template
stage: delivery-planning
gate: false
---

# Delivery Plan Templates

Use this skill after design review passes.

## Position

```text
technical_design + architecture_design
-> design-architecture-reviewer pass
-> delivery-plan-templates
-> delivery-state git gate
-> edit readiness
-> implementation
```

## Rules

- Generate a `delivery_plan.json` before Git branch preparation.
- Carry `requirements_understanding_gate` from technical/architecture design into `source_design_gate`; if `design_allowed=false` or `implementation_allowed=false`, keep the plan `needs_completion` with unresolved `open_gates`.
- Every repository must have one role: `modify`, `read_only`, `confirm_only`, or `out_of_scope`.
- Only `modify` repositories may be passed to `git-worktree-governor prepare-plan`.
- Every `modify` repository must include `repo_path` before execution in a real workspace.
- For registered projects, prefer the local checkout resolved from `${CODEX_HOME:-~/.codex}/skills/company/projects.yaml`; project-understanding `_staging` paths are evidence sources, not editable repository paths.
- Every `modify` repository should include `tasks`, `allowed_files`, `read_first`, `test_commands`, and `acceptance_evidence`.
- Every modify task should include files to read/edit, implementation notes, evidence to collect, rollback check, dependencies, blocking conditions, and exit criteria.
- `allowed_files` and `files_to_edit` should be real file paths from code index, module topology, or explicit human confirmation; do not broaden edit scope with unrelated read-first files.
- When source-location evidence exists, restrict `allowed_files` to confirmed anchors and emit an open gate for every unconfirmed or rejected module.
- Include Git preparation steps before edits: fetch, `pull --ff-only`, branch preparation, and clean worktree verification.
- File scope should be narrow enough for `edit-readiness-governor` and `workspace-write-guard`.
- Include cross-repo order, validation order, release order, rollback order, and open gates.
- Dependency edges and contract freeze points must reference repositories declared in `repo_tasks`.
- If technical or architecture design carries a requirement-declared repo map, every declared repo must appear in `repo_tasks`. A missing repo is an unresolved `open_gates` item, not a reason to silently emit a single-repo ready plan.
- Multiple `modify` repositories must require a cross-repo graph, gated parallel group, or serial group before execution.
- Do not start implementation while `open_gates` has unresolved items.
- Do not start Git preparation or edits when `source_design_gate` says requirement understanding is blocked.
- Treat missing `repo_path`, `_staging` modify paths without a resolvable registered checkout, weak file scope, unresolved dependencies, or unresolved open gates as blockers for implementation readiness.
- Treat incomplete test, rollback, validation, or release evidence planning as warnings until the delivery-plan reviewer upgrades them to blockers.

## Commands

Generate from design artifacts:

```bash
python3 scripts/render_delivery_plan.py \
  --doc-id REQ-001-checkout \
  --technical-design artifacts/design/technical_design.json \
  --architecture-design artifacts/design/architecture_design.json \
  --out artifacts/delivery_plan.json
```

Generate a synthetic example:

```bash
python3 scripts/render_delivery_plan.py \
  --doc-id REQ-EXAMPLE \
  --example \
  --out artifacts/example_delivery_plan.json
```

Validate:

```bash
python3 scripts/render_delivery_plan.py \
  validate \
  --file artifacts/delivery_plan.json
```

## Output

The output uses schema `codex-delivery-plan-v1`.

Decision values:

- `ready`: the plan has concrete repo tasks, scoped files, sequencing, validation, rollback, and no unresolved open gates.
- `needs_revision`: the plan is structurally usable but has warnings that must be resolved before edit readiness.
- `block`: required repository scope, dependency ordering, allowed files, or open-gate handling is missing.

Key consumers:

- `git-worktree-governor prepare-plan` reads `repo_tasks[].role=modify` and `repo_tasks[].repo_path`.
- `edit-readiness-governor` uses `allowed_files` and delivery plan scope.
- `workspace-write-guard` enforces the final permit file scope.
- CI/release skills can use test, validation, release, and rollback sections.
