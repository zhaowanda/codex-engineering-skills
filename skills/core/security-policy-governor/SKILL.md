---
name: security-policy-governor
description: Govern open-source security policy readiness. Use when adding or reviewing SECURITY.md, vulnerability reporting process, supported versions, private data rules, secret handling, privacy scan expectations, dependency license checks, or security response commitments.
---

# Security Policy Governor

Use this skill before publishing the repository or accepting security-sensitive changes.

## Command

```bash
python3 skills/core/security-policy-governor/scripts/security_policy.py --root .
```

## Rules

- `SECURITY.md` must exist.
- It must describe vulnerability reporting, supported versions, response process, private data rules, secrets, privacy scan, and dependency review.
- Security reports should not be filed through public issues when sensitive.

## Output

The output uses schema `codex-security-policy-v1`.
