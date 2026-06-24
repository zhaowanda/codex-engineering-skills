---
name: issue-pr-governor
description: Govern open-source GitHub issue and pull request readiness for engineering-skill changes. Use when creating issue templates, preparing PR descriptions, reviewing PR evidence, or checking whether a contribution has linked issue, scope, tests, risks, rollback, and release notes.
---

# Issue PR Governor

Use this skill before opening or merging a pull request.

## Command

```bash
python3 skills/core/issue-pr-governor/scripts/issue_pr.py \
  --pr-file .github/pull_request_template.md
```

## Rules

- PRs must describe scope, linked issue, tests, evidence, risk, rollback, and release notes.
- Bug reports must capture reproduction, expected behavior, actual behavior, environment, and logs/screenshots.
- Feature requests must capture problem, proposed behavior, acceptance criteria, alternatives, and compatibility.

## Output

The output uses schema `codex-issue-pr-governance-v1`.
