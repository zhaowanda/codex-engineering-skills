---
name: issue-pr-governor
description: Govern open-source GitHub issue and pull request readiness for engineering-skill changes. Use when creating issue templates, preparing PR descriptions, reviewing PR evidence, or checking whether a contribution has linked issue, scope, tests, risks, rollback, and release notes.
---

# Issue PR Governor

Use this skill before opening or merging a pull request.

## Position

```text
issue or pull request preparation
-> issue-pr-governor
-> contribution-governor
-> maintainer review
```

## Command

```bash
python3 scripts/issue_pr.py \
  --pr-file .github/pull_request_template.md
```

## Rules

- PRs must describe scope, linked issue, tests, evidence, risk, rollback, and release notes.
- Bug reports must capture reproduction, expected behavior, actual behavior, environment, and logs/screenshots.
- Feature requests must capture problem, proposed behavior, acceptance criteria, alternatives, and compatibility.
- Missing tests or evidence should request changes before merge.
- High-risk PRs should include rollback and compatibility notes.

## Output

The output uses schema `codex-issue-pr-governance-v1`.

The artifact reports PR-template readiness, issue-template readiness, required evidence coverage, blockers, warnings, and contribution follow-up items.
