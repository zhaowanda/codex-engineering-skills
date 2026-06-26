---
name: requirement-question-governor
description: Generate and validate open requirement questions before design or implementation. Use when spec-governor finds ambiguity, product docs contain TBDs, acceptance criteria are missing, or Codex must stop instead of guessing.
---

# Requirement Question Governor

Use this skill after ingestion/spec normalization and before design.

## Command

```bash
python3 scripts/question_governor.py \
  generate \
  --spec artifacts/REQ-001/spec.json \
  --out artifacts/REQ-001/open_questions.json
```

Validate answers:

```bash
python3 scripts/question_governor.py \
  validate \
  --file artifacts/REQ-001/open_questions.json
```

## Rules

- Block design/implementation while required questions are open.
- Ask focused questions only; do not ask for information already present in the spec.
- Track owner, required flag, answer, and status.

## Output

The output uses schema `codex-open-questions-v1`.
