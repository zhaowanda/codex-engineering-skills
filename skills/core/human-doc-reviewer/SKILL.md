---
name: human-doc-reviewer
description: Review human-readable delivery documents for clarity, substance, decision traceability, option comparison, risk explanation, evidence references, and local path leakage. Use before sharing design, release, baseline, or case documents across teams.
category: meta-governor
maturity: deterministic-helper
stage: documentation
gate: false
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
- Check formal document substance: background, goals, clarification, decisions, acceptance, tests, diagrams or explicit diagram gaps, release/rollback readiness, and machine evidence references.
- For design documents, check business process flowcharts and system sequence diagrams independently; strict review blocks when either Mermaid diagram type is missing.
- Require per-BRK concrete API bindings only when API modification is applicable. For an explicitly excluded or contract-confirm-only API surface, require one unchanged-contract statement plus at least one referenced existing path.
- For Chinese documents, warn when common English template headings remain.
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
