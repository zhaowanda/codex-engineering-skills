---
name: traceability-governor
description: Build and validate requirement-to-delivery traceability across requirements, acceptance criteria, technical design, architecture design, delivery plan, implementation diff, test design, and evidence. Use before implementation, before review, or before release to prevent untracked work and uncovered acceptance criteria.
---

# Traceability Governor

Use this skill when a delivery needs proof that every requirement and acceptance criterion is carried through design, tasks, implementation, tests, and evidence.

## Commands

```bash
python3 skills/core/traceability-governor/scripts/traceability.py \
  --artifact-dir artifacts/REQ-001 \
  --out artifacts/REQ-001/traceability_matrix.json
```

```bash
python3 skills/core/traceability-governor/scripts/traceability.py \
  --artifact-dir artifacts/REQ-001 \
  --validate
```

## Rules

- Every acceptance criterion should map to at least one test case.
- Every modify task should have allowed file scope and validation evidence.
- Implementation diff should not exist without a delivery plan.
- Release should not proceed with uncovered acceptance criteria or changed files outside traceability evidence.

## Output

The output uses schema `codex-traceability-matrix-v1`.
