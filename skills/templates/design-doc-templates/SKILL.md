---
name: design-doc-templates
description: Generate technical design and architecture design JSON artifacts that are compatible with the design-architecture-reviewer gate. Use when drafting design-first delivery artifacts before delivery planning, Git preparation, edit readiness, or implementation.
---

# Design Doc Templates

Use this skill to create design artifacts before implementation.

## Position

```text
spec
-> design-doc-templates
-> design-architecture-reviewer
-> delivery_plan
-> implementation gates
```

## Rules

- Generate both `technical_design.json` and `architecture_design.json`.
- Fill every generated section with concrete project facts before review.
- Do not leave placeholders such as `TBD`, `unknown`, or `confirm later`.
- Include at least two technical solution options and two architecture options.
- Include selected option, decision criteria, tradeoffs, and rejected alternative reasoning.
- Include process flow, data flow, module split, API/UI impact decisions, security, performance, rollback, observability, and tests.
- Run `design-architecture-reviewer` after filling the templates.

## Commands

Generate empty templates:

```bash
python3 skills/templates/design-doc-templates/scripts/render_design_templates.py \
  --doc-id REQ-001-checkout \
  --title "Checkout discount display" \
  --out-dir artifacts/design
```

Generate a complete synthetic example:

```bash
python3 skills/templates/design-doc-templates/scripts/render_design_templates.py \
  --doc-id REQ-EXAMPLE \
  --title "Checkout discount display" \
  --out-dir artifacts/design-example \
  --example
```

Review generated artifacts:

```bash
python3 skills/core/design-architecture-reviewer/scripts/design_arch_review.py \
  review \
  --technical-design artifacts/design/technical_design.json \
  --architecture-design artifacts/design/architecture_design.json \
  --out artifacts/design/design_architecture_review.json
```

## Output

The renderer writes:

- `technical_design.json`
- `architecture_design.json`
- `design_template_manifest.json`

Empty templates are intentionally not implementation-ready. They are a structured workbench. The synthetic example should pass the design reviewer and is used as regression evidence.
