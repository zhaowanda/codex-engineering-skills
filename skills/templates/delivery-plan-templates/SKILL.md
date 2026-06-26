---
name: delivery-plan-templates
description: Generate delivery plan JSON artifacts from reviewed technical and architecture designs. Use after design-architecture-reviewer passes and before Git preparation, edit readiness, implementation, testing, or release planning.
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
- Every repository must have one role: `modify`, `read_only`, `confirm_only`, or `out_of_scope`.
- Only `modify` repositories may be passed to `git-worktree-governor prepare-plan`.
- Every `modify` repository must include `repo_path` before execution in a real workspace.
- Every `modify` repository should include `tasks`, `allowed_files`, `read_first`, `test_commands`, and `acceptance_evidence`.
- File scope should be narrow enough for `edit-readiness-governor` and `workspace-write-guard`.
- Include cross-repo order, validation order, release order, rollback order, and open gates.
- Do not start implementation while `open_gates` has unresolved items.

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

Key consumers:

- `git-worktree-governor prepare-plan` reads `repo_tasks[].role=modify` and `repo_tasks[].repo_path`.
- `edit-readiness-governor` uses `allowed_files` and delivery plan scope.
- `workspace-write-guard` enforces the final permit file scope.
- CI/release skills can use test, validation, release, and rollback sections.
