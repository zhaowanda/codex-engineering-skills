# Architecture

## Concept

The framework turns an AI coding assistant into a gated engineering workflow participant.

```text
requirement input
-> normalized spec
-> technical design
-> architecture design
-> delivery plan
-> Git baseline and feature branch
-> edit permit
-> implementation in allowed scope
-> design/code/security/performance review
-> tests and frontend acceptance
-> release evidence
-> post-change learning
```

## Key Design Decisions

- Human docs and machine JSON are separate.
- Skills provide workflow knowledge; scripts provide deterministic gates.
- Project-specific knowledge is an overlay, not part of the open core.
- Source-code indexes are generated assets and must stay private by default.
- The platform command should answer: current stage, blockers, next command, and whether coding/release is allowed.

## Extension Points

- Project registry adapter.
- Docs repository adapter.
- CI provider templates.
- Browser acceptance provider.
- Semantic knowledge provider.
- Privacy pattern configuration.

