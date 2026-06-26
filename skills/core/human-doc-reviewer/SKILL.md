---
name: human-doc-reviewer
description: Review human-readable delivery documents for clarity, substance, decision traceability, option comparison, risk explanation, evidence references, and local path leakage. Use before sharing design, release, baseline, or case documents across teams.
---

# Human Doc Reviewer

Use this skill before sharing generated or hand-written delivery documents with reviewers.

## Position

```text
human-readable artifact draft
-> human-doc-reviewer
-> artifact-splitter / release evidence / team review
```

## Rules

- Check for clear scope, decisions, option comparison, risks, evidence references, rollback notes, and unresolved questions.
- Block local absolute paths, private markers, secrets, customer identifiers, or proprietary hostnames.
- Warn on thin documents that are readable but lack enough decision context.
- Do not validate machine-readable schema; use artifact-schema-governor for that.
- Treat review output as documentation quality evidence, not product approval.

## Command

```bash
python3 scripts/human_doc_review.py \
  --file docs/design.md
```

## Output

The output uses schema `codex-human-doc-review-v1`.

The artifact reports decision, blockers, warnings, checked dimensions, and remediation hints.
