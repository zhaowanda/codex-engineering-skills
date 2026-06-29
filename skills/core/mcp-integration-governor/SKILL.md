---
name: mcp-integration-governor
description: Govern generic MCP integration readiness and evidence for open-core workflows. Use when documenting or validating Chrome DevTools, GitHub, filesystem, knowledge, API, or browser MCP usage boundaries, acceptance evidence, and safe fallback rules.
category: meta-governor
maturity: deterministic-helper
stage: meta
gate: false
---

# MCP Integration Governor

Use this skill when a workflow or scenario depends on MCP tool evidence.

## Command

```bash
python3 scripts/mcp_integration.py --root .
```

## Rules

- Frontend scenarios should mention browser or Chrome DevTools acceptance.
- GitHub contribution flows should mention issue or PR evidence.
- MCP guidance must describe boundaries, evidence, and fallback.

## Output

The output uses schema `codex-mcp-integration-v1`.
